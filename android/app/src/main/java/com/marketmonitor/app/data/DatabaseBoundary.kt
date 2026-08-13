package com.marketmonitor.app.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Room
import com.marketmonitor.app.trading.CashEventEntity
import com.marketmonitor.app.trading.FeeEntity
import com.marketmonitor.app.trading.LedgerImportEntity
import com.marketmonitor.app.trading.PositionSnapshotEntity
import com.marketmonitor.app.trading.SplitEventEntity
import com.marketmonitor.app.trading.StrategyEntity
import com.marketmonitor.app.trading.TradeEntity
import com.marketmonitor.app.trading.TradingDao
import com.marketmonitor.app.trading.TradingMigrations
import net.zetetic.database.sqlcipher.SupportOpenHelperFactory
import java.io.File
import java.security.KeyStore
import java.security.SecureRandom
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator

object DatabaseBoundary {
    const val userDatabaseName = "user.db"
    const val marketDatabaseName = "market_hot.db"
    const val marketColdDirectory = "market-cold"

    fun userDatabaseFile(context: Context): File = context.getDatabasePath(userDatabaseName)
    fun marketDatabaseFile(context: Context): File = context.getDatabasePath(marketDatabaseName)
    fun coldDirectory(context: Context): File = File(context.filesDir, marketColdDirectory)

    fun deleteMarketData(context: Context) {
        marketDatabaseFile(context).delete()
        coldDirectory(context).deleteRecursively()
    }
}

class UserDatabaseKeyManager {
    fun ensureWrappingKey() {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (keyStore.containsAlias(KEY_ALIAS)) return
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            ).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build(),
        )
        generator.generateKey()
    }

    fun passphrase(context: Context): ByteArray {
        ensureWrappingKey()
        val preferences = context.getSharedPreferences("user-db-key", Context.MODE_PRIVATE)
        val encrypted = preferences.getString("ciphertext", null)
        val iv = preferences.getString("iv", null)
        if (encrypted != null && iv != null) return decrypt(encrypted, iv)
        val secret = ByteArray(32).also(SecureRandom()::nextBytes)
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val key = keyStore.getKey(KEY_ALIAS, null)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
        preferences.edit()
            .putString("ciphertext", Base64.getEncoder().encodeToString(cipher.doFinal(secret)))
            .putString("iv", Base64.getEncoder().encodeToString(cipher.iv))
            .apply()
        return secret
    }

    private fun decrypt(ciphertext: String, iv: String): ByteArray {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val key = keyStore.getKey(KEY_ALIAS, null)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key, javax.crypto.spec.GCMParameterSpec(128, Base64.getDecoder().decode(iv)))
        }
        return cipher.doFinal(Base64.getDecoder().decode(ciphertext))
    }

    private companion object { const val KEY_ALIAS = "market-monitor-user-db-wrap-v1" }
}

@Entity(tableName = "watchlist")
data class WatchlistEntity(@PrimaryKey val instrumentId: String, val createdAt: String)

@Dao
interface WatchlistDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun add(item: WatchlistEntity)
    @Query("SELECT * FROM watchlist ORDER BY createdAt") suspend fun all(): List<WatchlistEntity>
    @Query("DELETE FROM watchlist WHERE instrumentId = :instrumentId") suspend fun remove(instrumentId: String)
}

@Database(
    entities = [
        WatchlistEntity::class,
        StrategyEntity::class,
        TradeEntity::class,
        FeeEntity::class,
        CashEventEntity::class,
        SplitEventEntity::class,
        PositionSnapshotEntity::class,
        LedgerImportEntity::class,
    ],
    version = 2,
    exportSchema = true,
)
abstract class UserDatabase : RoomDatabase() {
    abstract fun watchlistDao(): WatchlistDao
    abstract fun tradingDao(): TradingDao

    companion object {
        val MIGRATION_1_2 = TradingMigrations.MIGRATION_1_2
    }
}

@Entity(tableName = "market_package")
data class MarketPackageEntity(@PrimaryKey val packageId: String, val importedAt: String, val dataCutoff: String)

@Dao
interface MarketPackageDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun add(item: MarketPackageEntity)
    @Query("SELECT * FROM market_package ORDER BY importedAt DESC") suspend fun history(): List<MarketPackageEntity>
}

@Database(entities = [MarketPackageEntity::class], version = 1, exportSchema = true)
abstract class MarketHotDatabase : RoomDatabase() { abstract fun packageDao(): MarketPackageDao }

object DatabaseFactory {
    fun user(context: Context): UserDatabase {
        System.loadLibrary("sqlcipher")
        return Room.databaseBuilder(context, UserDatabase::class.java, DatabaseBoundary.userDatabaseName)
            .openHelperFactory(SupportOpenHelperFactory(UserDatabaseKeyManager().passphrase(context)))
            .addMigrations(UserDatabase.MIGRATION_1_2)
            .build()
    }

    fun market(context: Context): MarketHotDatabase = Room.databaseBuilder(context, MarketHotDatabase::class.java, DatabaseBoundary.marketDatabaseName).build()
}
