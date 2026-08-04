package com.marketmonitor.app

import com.marketmonitor.app.data.MarketPackageVerifier
import com.marketmonitor.app.data.PackageValidationError
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import java.io.File
import java.nio.charset.StandardCharsets
import java.security.KeyPairGenerator
import java.security.Signature
import java.util.Base64
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class MarketPackageVerifierTest {
    @Test
    fun verifierAcceptsSignedManifestAndRejectsDuplicateOrUnknownSchema() {
        val keys = KeyPairGenerator.getInstance("Ed25519").generateKeyPair()
        val pem = "-----BEGIN PUBLIC KEY-----\n${Base64.getEncoder().encodeToString(keys.public.encoded)}\n-----END PUBLIC KEY-----\n"
        val file = File.createTempFile("market-package", ".zip")
        val manifest = """{"package_id":"package-1","schema_version":1,"minimum_app_version":"0.1.0","partitions":[],"source_run_summaries":[]}""".toByteArray(StandardCharsets.UTF_8)
        val signature = Signature.getInstance("Ed25519").run { initSign(keys.private); update(manifest); sign() }
        ZipOutputStream(file.outputStream()).use { output ->
            output.putNextEntry(ZipEntry("manifest.json")); output.write(manifest); output.closeEntry()
            output.putNextEntry(ZipEntry("signature.ed25519")); output.write(signature); output.closeEntry()
        }
        val verifier = MarketPackageVerifier(pem, "0.1.0")
        val validResult = verifier.verify(file, Long.MAX_VALUE, emptySet())
        assertNotNull("valid package error=${validResult.error}", validResult.verified)
        assertEquals(PackageValidationError.DUPLICATE, verifier.verify(file, Long.MAX_VALUE, setOf("package-1")).error)

        val old = File.createTempFile("market-package-old", ".zip")
        val oldManifest = String(manifest).replace("\"schema_version\":1", "\"schema_version\":0").toByteArray()
        val oldSignature = Signature.getInstance("Ed25519").run { initSign(keys.private); update(oldManifest); sign() }
        ZipOutputStream(old.outputStream()).use { output ->
            output.putNextEntry(ZipEntry("manifest.json")); output.write(oldManifest); output.closeEntry()
            output.putNextEntry(ZipEntry("signature.ed25519")); output.write(oldSignature); output.closeEntry()
        }
        assertEquals(PackageValidationError.SCHEMA, verifier.verify(old, Long.MAX_VALUE, emptySet()).error)

    }
}
