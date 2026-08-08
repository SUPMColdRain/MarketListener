package com.marketmonitor.app.strategy.dsl

/** Stable machine-readable error categories shared by desktop and Android. */
enum class DslErrorKind {
    SCHEMA,
    UNKNOWN_NODE,
    CYCLE,
    LIMIT,
    NO_DATA,
    PARAMETER,
    TYPE,
    NUMERIC,
    TIMEOUT,
    CANCELLED,
}

class DslException(val kind: DslErrorKind, message: String) : Exception(message)
