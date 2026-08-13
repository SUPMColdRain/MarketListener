package com.marketmonitor.app.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.os.StatFs
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.GeneralSecurityException
import java.security.KeyFactory
import java.security.Signature
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.UUID
import java.util.zip.ZipException
import java.util.zip.ZipFile

enum class PackageValidationError { SIGNATURE, HASH, SCHEMA, SPACE, DUPLICATE, DOWNGRADE, STRUCTURE, PAYLOAD }

data class VerifiedMarketPackage(val packageId: String, val dataCutoff: String)
data class PackageValidationResult(
    val verified: VerifiedMarketPackage? = null,
    val error: PackageValidationError? = null,
    val errorDetail: String? = null,
)

class MarketPackageVerifier(
    private val publicKeyPem: String,
    private val appVersion: String,
    private val ecdsaPublicKeyPem: String? = null,
) {
    fun verify(packageFile: File, availableBytes: Long, importedPackageIds: Set<String>): PackageValidationResult {
        return try {
            ZipFile(packageFile).use { archive ->
                val names = archive.entries().asSequence().map { it.name }.toList()
                names.firstOrNull { it !in ALLOWED_ENTRIES }?.let { unexpected ->
                    return failure(PackageValidationError.STRUCTURE, "压缩包包含不允许的条目：$unexpected")
                }
                val manifestCount = names.count { it == "manifest.json" }
                val signatureCount = names.count { it == "signature.ed25519" } + names.count { it == "signature.ecdsa" }
                if (manifestCount != 1 || signatureCount == 0) {
                    return failure(PackageValidationError.STRUCTURE, "manifest.json 或签名条目数量不正确")
                }
                if (names.count { it == "signature.ed25519" } > 1 || names.count { it == "signature.ecdsa" } > 1) {
                    return failure(PackageValidationError.STRUCTURE, "签名条目重复")
                }
                val manifestEntry = archive.getEntry("manifest.json") ?: return failure(PackageValidationError.STRUCTURE, "缺少 manifest.json")
                val manifest = archive.getInputStream(manifestEntry).readBytes()
                if (!verifySignatures(manifest, archive, names)) {
                    return failure(PackageValidationError.SIGNATURE, "签名验证未通过（已尝试 Ed25519/ECDSA）")
                }
                val json = JSONObject(String(manifest, Charsets.UTF_8))
                if (json.optInt("schema_version", -1) != 1) return failure(PackageValidationError.SCHEMA, "不支持的 schema_version")
                val packageId = json.optString("package_id")
                if (packageId.isBlank()) return failure(PackageValidationError.STRUCTURE, "package_id 为空")
                if (packageId in importedPackageIds) return failure(PackageValidationError.DUPLICATE, "该行情包已导入")
                if (compareVersions(json.optString("minimum_app_version"), appVersion) > 0) {
                    return failure(PackageValidationError.DOWNGRADE, "行情包要求更高版本的 App")
                }
                if (packageFile.length() * 2 > availableBytes) {
                    return failure(PackageValidationError.SPACE, "设备可用空间不足")
                }
                val partitions = json.optJSONArray("partitions") ?: return failure(PackageValidationError.STRUCTURE, "manifest 缺少 partitions")
                var cutoff = ""
                for (index in 0 until partitions.length()) {
                    val partition = partitions.getJSONObject(index)
                    cutoff = maxOf(cutoff, partition.getString("data_cutoff"))
                    val files = partition.getJSONArray("files")
                    for (fileIndex in 0 until files.length()) {
                        val expected = files.getJSONObject(fileIndex)
                        val entry = archive.getEntry(expected.getString("name")) ?: return failure(PackageValidationError.HASH, "缺少数据文件")
                        val content = archive.getInputStream(entry).readBytes()
                        if (content.size.toLong() != expected.getLong("bytes") || sha256(content) != expected.getString("sha256")) {
                            return failure(PackageValidationError.HASH, "数据文件哈希校验未通过")
                        }
                    }
                }
                PackageValidationResult(VerifiedMarketPackage(packageId, cutoff))
            }
        } catch (error: ZipException) {
            failure(PackageValidationError.STRUCTURE, "压缩包损坏：${error.message}")
        } catch (error: JSONException) {
            failure(PackageValidationError.SCHEMA, "manifest 解析失败：${error.message}")
        } catch (error: GeneralSecurityException) {
            failure(PackageValidationError.SIGNATURE, "签名校验异常：${error.message}")
        } catch (error: SecurityException) {
            failure(PackageValidationError.STRUCTURE, error.message ?: "安全校验失败")
        } catch (error: Exception) {
            failure(PackageValidationError.STRUCTURE, error.message ?: error.javaClass.simpleName)
        }
    }

    private fun verifySignatures(manifest: ByteArray, archive: ZipFile, names: List<String>): Boolean {
        var verified = false
        var lastNote: String? = null
        if ("signature.ed25519" in names) {
            try {
                val signature = archive.getInputStream(archive.getEntry("signature.ed25519")).readBytes()
                verified = verifyEd25519(manifest, signature)
                if (!verified) lastNote = "Ed25519 签名不匹配"
            } catch (error: GeneralSecurityException) {
                lastNote = "Ed25519 不可用：${error.message}"
            }
        }
        if (!verified && "signature.ecdsa" in names) {
            try {
                if (ecdsaPublicKeyPem.isNullOrBlank()) {
                    lastNote = "缺少 ECDSA 公钥"
                } else {
                    val signature = archive.getInputStream(archive.getEntry("signature.ecdsa")).readBytes()
                    verified = verifyEcdsa(manifest, signature)
                    if (!verified) lastNote = "ECDSA 签名不匹配"
                }
            } catch (error: GeneralSecurityException) {
                lastNote = "ECDSA 校验异常：${error.message}"
            }
        }
        if (!verified && lastNote != null) {
            throw SecurityException(lastNote)
        }
        return verified
    }

    private fun verifyEd25519(manifest: ByteArray, signature: ByteArray): Boolean {
        val encoded = publicKeyPem.lines().filterNot { it.startsWith("---") }.joinToString("").trim()
        val key = KeyFactory.getInstance("Ed25519").generatePublic(X509EncodedKeySpec(Base64.getDecoder().decode(encoded)))
        return Signature.getInstance("Ed25519").run { initVerify(key); update(manifest); verify(signature) }
    }

    private fun verifyEcdsa(manifest: ByteArray, signature: ByteArray): Boolean {
        val encoded = ecdsaPublicKeyPem!!.lines().filterNot { it.startsWith("---") }.joinToString("").trim()
        val key = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(Base64.getDecoder().decode(encoded)))
        return Signature.getInstance("SHA256withECDSA").run { initVerify(key); update(manifest); verify(signature) }
    }

    private fun sha256(value: ByteArray): String = java.security.MessageDigest.getInstance("SHA-256").digest(value).joinToString("") { "%02x".format(it) }
    private fun failure(error: PackageValidationError, detail: String? = null) = PackageValidationResult(error = error, errorDetail = detail)

    companion object {
        private val ALLOWED_ENTRIES = setOf(
            "manifest.json",
            "quality-report.json",
            "payload.sqlite",
            "signature.ed25519",
            "signature.ecdsa",
            "industry/industry-map.html",
            "industry/industry-atlas.html",
        )
    }
}

class MarketPackageImporter(private val context: Context) {
    fun importPackage(packageFile: File): PackageValidationResult {
        val preferences = context.getSharedPreferences("market-package", Context.MODE_PRIVATE)
        val imported = preferences.getStringSet("imported", emptySet()).orEmpty()
        val verifier = MarketPackageVerifier(
            context.resources.openRawResource(com.marketmonitor.app.R.raw.market_package_public_key).bufferedReader().readText(),
            "0.1.0",
            ecdsaPublicKeyPem = runCatching {
                context.resources.openRawResource(com.marketmonitor.app.R.raw.market_package_ecdsa_public_key).bufferedReader().readText()
            }.getOrNull(),
        )
        val result = verifier.verify(packageFile, StatFs(context.filesDir.path).availableBytes, imported)
        val verified = result.verified ?: return result
        val root = DatabaseBoundary.coldDirectory(context)
        val staging = File(root, "staging-${UUID.randomUUID()}")
        val target = File(File(root, "packages"), verified.packageId)
        staging.mkdirs(); target.parentFile?.mkdirs()
        try {
            ZipFile(packageFile).use { archive -> archive.entries().asSequence().forEach { entry ->
                if (entry.isDirectory || entry.name !in EXTRACT_ENTRIES) return@forEach
                val destination = File(staging, entry.name)
                if (!destination.canonicalPath.startsWith(staging.canonicalPath + File.separator)) throw SecurityException("Zip path traversal")
                destination.parentFile?.mkdirs(); archive.getInputStream(entry).use { input -> destination.outputStream().use(input::copyTo) }
            } }
            validatePayload(File(staging, "payload.sqlite"))
            Files.move(staging.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE)
            preferences.edit()
                .putString("active", verified.packageId)
                .putString("active_cutoff", verified.dataCutoff)
                .putStringSet("imported", imported + verified.packageId)
                .apply()
            return result
        } catch (error: Exception) {
            staging.deleteRecursively()
            return PackageValidationResult(
                error = PackageValidationError.PAYLOAD,
                errorDetail = error.message ?: error.javaClass.simpleName,
            )
        }
    }

    private fun validatePayload(file: File) {
        SQLiteDatabase.openDatabase(file.path, null, SQLiteDatabase.OPEN_READONLY).use { database ->
            val foreignKeyViolations = database.rawQuery("PRAGMA foreign_key_check", null).use { cursor ->
                buildList { while (cursor.moveToNext()) add(cursor.getString(0)) }
            }
            require(foreignKeyViolations.isEmpty()) { "外键校验失败：$foreignKeyViolations" }
            require(database.rawQuery("SELECT count(*) FROM bars", null).use { it.moveToFirst() && it.getLong(0) >= 0 }) {
                "行情数据表 bars 不可用"
            }
        }
    }

    companion object {
        private val EXTRACT_ENTRIES = setOf(
            "manifest.json",
            "quality-report.json",
            "payload.sqlite",
            "industry/industry-map.html",
            "industry/industry-atlas.html",
        )
    }
}

class MarketPackageImportWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters) {
    override suspend fun doWork(): Result {
        val path = inputData.getString("package_path")
            ?: return Result.failure(workDataOf(RESULT_ERROR to PackageValidationError.STRUCTURE.name, RESULT_ERROR_DETAIL to "缺少 package_path"))
        val result = MarketPackageImporter(applicationContext).importPackage(File(path))
        val verified = result.verified
        return if (verified != null) {
            Result.success(
                workDataOf(
                    RESULT_PACKAGE_ID to verified.packageId,
                    RESULT_DATA_CUTOFF to verified.dataCutoff,
                ),
            )
        } else {
            Result.failure(
                workDataOf(
                    RESULT_ERROR to (result.error ?: PackageValidationError.STRUCTURE).name,
                    RESULT_ERROR_DETAIL to (result.errorDetail ?: "未知错误"),
                ),
            )
        }
    }

    companion object {
        const val RESULT_PACKAGE_ID = "package_id"
        const val RESULT_DATA_CUTOFF = "data_cutoff"
        const val RESULT_ERROR = "validation_error"
        const val RESULT_ERROR_DETAIL = "validation_error_detail"
    }
}

private fun compareVersions(left: String, right: String): Int {
    val leftParts = left.split('.').mapNotNull(String::toIntOrNull)
    val rightParts = right.split('.').mapNotNull(String::toIntOrNull)
    for (index in 0 until maxOf(leftParts.size, rightParts.size)) {
        val compare = (leftParts.getOrElse(index) { 0 }).compareTo(rightParts.getOrElse(index) { 0 })
        if (compare != 0) return compare
    }
    return 0
}
