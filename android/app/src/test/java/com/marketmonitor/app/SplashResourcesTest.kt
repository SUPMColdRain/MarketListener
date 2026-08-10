package com.marketmonitor.app

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class SplashResourcesTest {

    private fun resRoot(): File {
        val candidates = listOf(
            File("src/main/res"),
            File("../app/src/main/res"),
            File("android/app/src/main/res"),
            File("../../android/app/src/main/res"),
            File(System.getProperty("user.dir"), "src/main/res"),
        )
        return candidates.firstOrNull { it.isDirectory }
            ?: error("Cannot locate android res directory from ${System.getProperty("user.dir")}")
    }

    @Test
    fun splashThemeReferencesLogoPlaceholder() {
        val themes = File(resRoot(), "values/themes.xml")
        assertTrue(themes.isFile)
        val content = themes.readText()
        assertTrue(content.contains("Theme.SplashScreen"))
        assertTrue(content.contains("windowSplashScreenAnimatedIcon"))
        assertTrue(content.contains("@drawable/splash_logo_placeholder"))
        assertTrue(content.contains("postSplashScreenTheme"))
    }

    @Test
    fun splashAndLauncherDrawablesExist() {
        assertTrue(File(resRoot(), "drawable/splash_logo_placeholder.xml").isFile)
        assertTrue(File(resRoot(), "drawable/ic_launcher_foreground.xml").isFile)
        assertTrue(File(resRoot(), "mipmap-anydpi-v26/ic_launcher.xml").isFile)
        assertTrue(File(resRoot(), "mipmap-anydpi-v26/ic_launcher_round.xml").isFile)
    }

    @Test
    fun splashColorsAreDefined() {
        val colors = File(resRoot(), "values/colors.xml")
        assertTrue(colors.isFile)
        val content = colors.readText()
        assertTrue(content.contains("splash_background"))
        assertTrue(content.contains("launcher_background"))
    }
}
