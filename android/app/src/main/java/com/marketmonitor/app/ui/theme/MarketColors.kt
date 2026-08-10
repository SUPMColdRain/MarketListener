package com.marketmonitor.app.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * Semantic market colors. Default convention for A-share/HK/futures:
 * up = red, down = green, flat = gray. Future international preference changes
 * only these tokens.
 */
data class MarketColors(
    val priceUp: Color,
    val priceDown: Color,
    val flat: Color,
    val warning: Color,
    val error: Color,
    val info: Color,
    val highlight: Color,
) {
    companion object {
        val Dark = MarketColors(
            priceUp = Color(0xFFFF5A5F),
            priceDown = Color(0xFF2BBF8C),
            flat = Color(0xFF929EAF),
            warning = Color(0xFFF5A623),
            error = Color(0xFFFF6B6B),
            info = Color(0xFF4DA3FF),
            highlight = Color(0xFFFFD166),
        )

        val Light = MarketColors(
            priceUp = Color(0xFFD9383F),
            priceDown = Color(0xFF0E9F6E),
            flat = Color(0xFF687386),
            warning = Color(0xFFB7791F),
            error = Color(0xFFC62828),
            info = Color(0xFF2563EB),
            highlight = Color(0xFFB7791F),
        )
    }
}
