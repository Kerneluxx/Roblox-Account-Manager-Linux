THEME_COLORS = {
    "light": dict(window="#f5f5f5", base="#ffffff", text="#1b1b1b", button="#e9e9e9",
                  highlight="#0b5c7a", hltext="#ffffff", accent="#1f6f8b", accent_text="#ffffff"),
    "dark": dict(window="#202124", base="#17181a", text="#e8eaed", button="#2d2f33",
                 highlight="#5bb4d6", hltext="#101214", accent="#5bb4d6", accent_text="#101214"),
    "hc_dark": dict(window="#000000", base="#000000", text="#ffffff", button="#000000",
                    highlight="#ffff00", hltext="#000000", accent="#ffff00", accent_text="#000000"),
    "hc_light": dict(window="#ffffff", base="#ffffff", text="#000000", button="#ffffff",
                     highlight="#000080", hltext="#ffffff", accent="#000080", accent_text="#ffffff"),
}
SYSTEM_ACCENT = ("#1f6f8b", "#ffffff")


def contrast_ratio(foreground, background):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        channels = [
            value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)
