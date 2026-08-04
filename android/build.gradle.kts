plugins {
    id("com.android.application") version "8.3.2" apply false
    id("org.jetbrains.kotlin.android") version "2.0.0" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.0.0" apply false
    id("org.jetbrains.kotlin.kapt") version "2.0.0" apply false
}

if (JavaVersion.current() != JavaVersion.VERSION_21) {
    throw GradleException(
        "This project requires JDK 21 to run Gradle; current runtime is ${System.getProperty("java.version")}",
    )
}

allprojects {
    dependencyLocking {
        lockAllConfigurations()
    }
}
