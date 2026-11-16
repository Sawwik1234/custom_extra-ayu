"""Minimal localization layer.

Keeps the same call style as ``elyx.Strings`` (``i18n.t("key", name=...)``) so the
plugin can be moved to Elyx locales later without touching call sites.
"""

from __future__ import annotations

import locale as _locale
from typing import Any, Dict, Optional

_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "plugin_description": "Live chat wallpapers, custom themes and skins for exteraGram.",
        # generic
        "on": "On",
        "off": "Off",
        "page_diagnostics": "Diagnostics",
        "page_performance": "Performance",
        # wallpaper page
        "header_wallpaper": "Live wallpaper",
        "wallpaper_enabled": "Live wallpaper",
        "wallpaper_enabled_sub": "Master switch for the animated background",
        "wallpaper_kind": "Animation type",
        "wallpaper_kind_sub": "How the background is drawn",
        "kind_gradient": "Animated gradient",
        "kind_parallax": "Parallax image",
        "kind_particles": "Particles",
        "kind_video": "Video / GIF loop",
        "wallpaper_apply_chat": "Show in chats",
        "wallpaper_apply_dialogs": "Show in chat list",
        "wallpaper_apply_everywhere": "Show everywhere",
        "wallpaper_apply_everywhere_sub": "Also on other screens of the app",
        "wallpaper_source": "Background source",
        "wallpaper_source_sub": "Built-in, file or URL",
        "source_builtin": "Built-in",
        "source_file": "File",
        "source_url": "URL",
        "wallpaper_builtin": "Built-in background",
        "wallpaper_url": "Image / video URL",
        "wallpaper_url_sub": "Tap to download, long tap to clear the cache",
        "wallpaper_pick_file": "Pick from gallery",
        "wallpaper_folder_pick": "Pick from plugin folder",
        "wallpaper_folder_pick_sub": "Files placed in plugins/custom_extra_ayu/backgrounds",

        "wallpaper_pick_file_sub": "Choose an image, GIF or video",
        "wallpaper_reload": "Reload background",
        "wallpaper_reload_sub": "Re-download and re-decode",
        "wallpaper_current": "Current source",
        "wallpaper_missing": "No background loaded yet",
        "wallpaper_state_ok": "Ready",
        "wallpaper_state_error": "Failed: {error}",
        # appearance
        "header_look": "Look",
        "wallpaper_dim": "Dimming",
        "wallpaper_dim_sub": "0 — no dimming, 100 — nearly black",
        "wallpaper_blur": "Blur",
        "wallpaper_blur_sub": "0 — off, high values are expensive",
        "wallpaper_speed": "Animation speed",
        "wallpaper_speed_sub": "Percent of the normal speed",
        "wallpaper_scale": "Scale",
        "wallpaper_scale_sub": "Percent of the screen size",
        "wallpaper_offset_x": "Horizontal offset",
        "wallpaper_offset_y": "Vertical offset",
        "wallpaper_fade": "Smooth transitions",
        "wallpaper_fade_sub": "Fade the background in on screen changes",
        "wallpaper_fade_duration": "Transition duration",
        "wallpaper_fade_duration_sub": "Milliseconds",
        "wallpaper_tint": "Dark theme dimming",
        "wallpaper_tint_sub": "Extra dimming when the app uses a dark theme",
        # particles
        "header_particles": "Particles",
        "particles_type": "Effect",
        "particles_type_sub": "Shape and motion of the particles",
        "particles_snow": "Snow",
        "particles_stars": "Stars",
        "particles_bubbles": "Bubbles",
        "particles_rain": "Rain",
        "particles_count": "Amount",
        "particles_count_sub": "Higher values cost more battery",
        "particles_size": "Size",
        "particles_speed": "Speed",
        "particles_alpha": "Opacity",
        "particles_color": "Color",
        "particles_color_sub": "Hex color, for example #FFFFFF",
        # per chat
        "header_per_chat": "Chats with custom backgrounds",
        "per_chat_empty": "No chat overrides yet",
        "per_chat_empty_sub": "Use a chat menu item to assign a background",
        "per_chat_reset_all": "Reset all overrides",
        "per_chat_count": "Overrides: {count}",
        "per_chat_dialog": "Background for this chat",
        "per_chat_inherit": "Use global background",
        "per_chat_custom": "Custom for this chat",
        "per_chat_saved": "Background saved for the chat",
        "per_chat_reset_one": "Remove this override",

        "per_chat_cleared": "Custom background removed",
        # themes
        "header_themes": "Themes",
        "theme_active": "Active theme",
        "theme_active_sub": "Applied to the current look",
        "theme_none": "Default look",
        "theme_create": "Create theme from current look",
        "theme_new_name": "New theme",
        "theme_preview_header": "Preview",
        "theme_accent": "Accent color",
        "theme_accent_sub": "Hex color, for example #7C4DFF",
        "theme_out_bubble": "Outgoing bubble",
        "theme_in_bubble": "Incoming bubble",
        "theme_bubbles_alpha": "Bubble opacity",
        "theme_header_color": "Header color",
        "theme_page_color": "Background color",
        "theme_apply": "Apply theme",
        "theme_apply_sub": "Applies colors without restarting the app",
        "theme_import": "Import theme",
        "theme_import_sub": "Pick a theme JSON file",
        "theme_reset": "Reset applied colors",
        "theme_delete": "Delete theme",
        "theme_saved": "Theme applied",
        "theme_reset_done": "Colors restored",
        "theme_deleted": "Theme deleted",
        "theme_invalid_color": "Invalid color value",
        "theme_list_empty": "No themes yet",
        "theme_list_empty_sub": "Create one from the current look",
        # skins
        "header_skins": "Skins",
        "skins_enabled": "Enable skins",
        "skins_enabled_sub": "Replace bubble and panel textures",
        "skins_mode": "Mode",
        "skins_mode_sub": "Texture replacement needs client support",
        "skins_mode_tint": "Colors and gradients",
        "skins_mode_texture": "Texture replacement",
        "skins_mode_auto": "Automatic",
        "skin_active": "Active skin",
        "skin_none": "None",
        "skin_create": "Create skin folder",
        "skin_import_hint": "Put images into the skin folder and tap reload",
        "skin_import": "Import skin",
        "skin_import_sub": "Pick skin.json with its images",
        "skin_reload": "Reload skin",
        "skin_state": "Skin status",
        "skin_state_ok": "Loaded: {count} elements",
        "skin_state_missing": "Skin folder not found",
        "skin_element_out": "Outgoing bubble",
        "skin_element_in": "Incoming bubble",
        "skin_element_panel": "Input panel",
        "skin_element_header": "Header",
        # performance
        "header_perf_general": "Rendering",
        "perf_fps": "Frame rate limit",
        "perf_fps_sub": "Lower values save battery",
        "perf_quality": "Texture quality",
        "perf_quality_sub": "Lower resolution uses less memory",
        "perf_pause_scroll": "Pause while scrolling",
        "perf_pause_idle": "Pause when idle",
        "perf_pause_idle_delay": "Idle timeout",
        "perf_pause_idle_delay_sub": "Seconds without interaction",
        "perf_pause_background": "Pause in background",
        "perf_eco": "Economy mode",
        "perf_eco_sub": "One switch: 30 FPS, pauses, half resolution",
        "perf_active": "Rendering now: {state}",
        "perf_state_running": "yes",
        "perf_state_paused": "paused",
        "perf_state_off": "no",
        # diagnostics
        "diag_header_env": "Environment",
        "diag_client": "Client version",
        "diag_android": "Android",
        "diag_sdk": "Plugin SDK",
        "diag_headers": "Client internals",
        "diag_headers_sub": "Hooks found by reflection",
        "diag_copy_log": "Copy log",
        "diag_copy_log_sub": "Copies recent plugin log lines",
        "diag_copied": "Log copied",
        "diag_reset": "Reset all settings",
        "diag_reset_sub": "Restores defaults, keeps files",
        "diag_reset_done": "Settings reset",
        "diag_ok": "available",
        "diag_fail": "not available",
        "diag_hook_bound": "bound",
        "diag_hook_missing": "missing",
        "diag_events_seen": "Hook events: {count}",
        "diag_last_error": "Last error: {error}",
        "diag_no_errors": "No errors",
    },
    "ru": {
        "plugin_description": "Живые обои в чатах, свои темы и скины для exteraGram.",
        "on": "Вкл",
        "off": "Выкл",
        "page_diagnostics": "Диагностика",
        "page_performance": "Производительность",
        "header_wallpaper": "Живые обои",
        "wallpaper_enabled": "Живые обои",
        "wallpaper_enabled_sub": "Главный выключатель анимированного фона",
        "wallpaper_kind": "Тип анимации",
        "wallpaper_kind_sub": "Как рисуется фон",
        "kind_gradient": "Анимированный градиент",
        "kind_parallax": "Параллакс-картинка",
        "kind_particles": "Частицы",
        "kind_video": "Видео / GIF-цикл",
        "wallpaper_apply_chat": "Показывать в чатах",
        "wallpaper_apply_dialogs": "Показывать в списке чатов",
        "wallpaper_apply_everywhere": "Показывать везде",
        "wallpaper_apply_everywhere_sub": "Ещё и на остальных экранах приложения",
        "wallpaper_source": "Источник фона",
        "wallpaper_source_sub": "Встроенный, файл или ссылка",
        "source_builtin": "Встроенный",
        "source_file": "Файл",
        "source_url": "Ссылка",
        "wallpaper_builtin": "Встроенный фон",
        "wallpaper_url": "Ссылка на картинку / видео",
        "wallpaper_url_sub": "Тап — скачать, долгий тап — очистить кэш",
        "wallpaper_pick_file": "Выбрать из галереи",
        "wallpaper_folder_pick": "Выбрать из папки плагина",
        "wallpaper_folder_pick_sub": "Файлы из plugins/custom_extra_ayu/backgrounds",

        "wallpaper_pick_file_sub": "Картинка, GIF или видео",
        "wallpaper_reload": "Перезагрузить фон",
        "wallpaper_reload_sub": "Скачать и декодировать заново",
        "wallpaper_current": "Текущий источник",
        "wallpaper_missing": "Фон ещё не загружен",
        "wallpaper_state_ok": "Готово",
        "wallpaper_state_error": "Ошибка: {error}",
        "header_look": "Внешний вид",
        "wallpaper_dim": "Затемнение",
        "wallpaper_dim_sub": "0 — без затемнения, 100 — почти чёрный",
        "wallpaper_blur": "Размытие",
        "wallpaper_blur_sub": "0 — выключено, большие значения дорогие",
        "wallpaper_speed": "Скорость анимации",
        "wallpaper_speed_sub": "Проценты от обычной скорости",
        "wallpaper_scale": "Масштаб",
        "wallpaper_scale_sub": "Проценты от размера экрана",
        "wallpaper_offset_x": "Сдвиг по горизонтали",
        "wallpaper_offset_y": "Сдвиг по вертикали",
        "wallpaper_fade": "Плавные переходы",
        "wallpaper_fade_sub": "Плавное появление фона при смене экрана",
        "wallpaper_fade_duration": "Длительность перехода",
        "wallpaper_fade_duration_sub": "Миллисекунды",
        "wallpaper_tint": "Затемнение в тёмной теме",
        "wallpaper_tint_sub": "Дополнительное затемнение при тёмной теме",
        "header_particles": "Частицы",
        "particles_type": "Эффект",
        "particles_type_sub": "Форма и движение частиц",
        "particles_snow": "Снег",
        "particles_stars": "Звёзды",
        "particles_bubbles": "Пузырьки",
        "particles_rain": "Дождь",
        "particles_count": "Количество",
        "particles_count_sub": "Чем больше, тем дороже для батареи",
        "particles_size": "Размер",
        "particles_speed": "Скорость",
        "particles_alpha": "Прозрачность",
        "particles_color": "Цвет",
        "particles_color_sub": "Hex-цвет, например #FFFFFF",
        "header_per_chat": "Чаты с особыми обоями",
        "per_chat_empty": "Переопределений пока нет",
        "per_chat_empty_sub": "Задайте фон через меню чата",
        "per_chat_reset_all": "Сбросить все переопределения",
        "per_chat_count": "Переопределений: {count}",
        "per_chat_dialog": "Фон для этого чата",
        "per_chat_inherit": "Как глобальный",
        "per_chat_custom": "Свой для этого чата",
        "per_chat_saved": "Фон для чата сохранён",
        "per_chat_reset_one": "Удалить это переопределение",

        "per_chat_cleared": "Свой фон удалён",
        "header_themes": "Темы",
        "theme_active": "Активная тема",
        "theme_active_sub": "Применена к текущему оформлению",
        "theme_none": "Стандартное оформление",
        "theme_create": "Создать тему из текущего вида",
        "theme_new_name": "Новая тема",
        "theme_preview_header": "Превью",
        "theme_accent": "Акцентный цвет",
        "theme_accent_sub": "Hex-цвет, например #7C4DFF",
        "theme_out_bubble": "Исходящее сообщение",
        "theme_in_bubble": "Входящее сообщение",
        "theme_bubbles_alpha": "Прозрачность пузырей",
        "theme_header_color": "Цвет шапки",
        "theme_page_color": "Цвет фона",
        "theme_apply": "Применить тему",
        "theme_apply_sub": "Цвета применяются без перезапуска",
        "theme_import": "Импортировать тему",
        "theme_import_sub": "Выберите JSON-файл темы",
        "theme_reset": "Сбросить цвета",
        "theme_delete": "Удалить тему",
        "theme_saved": "Тема применена",
        "theme_reset_done": "Цвета восстановлены",
        "theme_deleted": "Тема удалена",
        "theme_invalid_color": "Неверный цвет",
        "theme_list_empty": "Тем пока нет",
        "theme_list_empty_sub": "Создайте тему из текущего вида",
        "header_skins": "Скины",
        "skins_enabled": "Включить скины",
        "skins_enabled_sub": "Подмена текстур пузырей и панелей",
        "skins_mode": "Режим",
        "skins_mode_sub": "Подмена текстур требует поддержки клиента",
        "skins_mode_tint": "Цвета и градиенты",
        "skins_mode_texture": "Подмена текстур",
        "skins_mode_auto": "Автоматически",
        "skin_active": "Активный скин",
        "skin_none": "Нет",
        "skin_create": "Создать папку скина",
        "skin_import_hint": "Положите картинки в папку скина и нажмите перезагрузку",
        "skin_import": "Импортировать скин",
        "skin_import_sub": "Выберите skin.json вместе с картинками",
        "skin_reload": "Перезагрузить скин",
        "skin_state": "Состояние скина",
        "skin_state_ok": "Загружено элементов: {count}",
        "skin_state_missing": "Папка скина не найдена",
        "skin_element_out": "Исходящий пузырь",
        "skin_element_in": "Входящий пузырь",
        "skin_element_panel": "Панель ввода",
        "skin_element_header": "Шапка",
        "header_perf_general": "Отрисовка",
        "perf_fps": "Лимит кадров",
        "perf_fps_sub": "Меньше — экономнее для батареи",
        "perf_quality": "Качество текстуры",
        "perf_quality_sub": "Ниже разрешение — меньше памяти",
        "perf_pause_scroll": "Пауза при скролле",
        "perf_pause_idle": "Пауза при бездействии",
        "perf_pause_idle_delay": "Таймаут бездействия",
        "perf_pause_idle_delay_sub": "Секунд без действий",
        "perf_pause_background": "Пауза в фоне",
        "perf_eco": "Экономный режим",
        "perf_eco_sub": "Один переключатель: 30 FPS, паузы, половина разрешения",
        "perf_active": "Сейчас рисуется: {state}",
        "perf_state_running": "да",
        "perf_state_paused": "пауза",
        "perf_state_off": "нет",
        "diag_header_env": "Окружение",
        "diag_client": "Версия клиента",
        "diag_android": "Android",
        "diag_sdk": "SDK плагинов",
        "diag_headers": "Внутренности клиента",
        "diag_headers_sub": "Найденные хуки через рефлексию",
        "diag_copy_log": "Скопировать лог",
        "diag_copy_log_sub": "Копирует последние строки лога плагина",
        "diag_copied": "Лог скопирован",
        "diag_reset": "Сбросить все настройки",
        "diag_reset_sub": "Возвращает значения по умолчанию, файлы остаются",
        "diag_reset_done": "Настройки сброшены",
        "diag_ok": "доступно",
        "diag_fail": "недоступно",
        "diag_hook_bound": "подключен",
        "diag_hook_missing": "не найден",
        "diag_events_seen": "Событий хуков: {count}",
        "diag_last_error": "Последняя ошибка: {error}",
        "diag_no_errors": "Ошибок нет",
    },
}

_current: str = "en"


def _detect_locale() -> str:
    """Return a supported locale code for the system language."""
    candidates = []
    try:
        candidates.append(_locale.getdefaultlocale()[0])
    except Exception:
        pass
    try:
        candidates.append(_locale.getlocale()[0])
    except Exception:
        pass
    for value in candidates:
        if not value:
            continue
        code = str(value).replace("-", "_").split("_")[0].lower()
        if code in _STRINGS:
            return code
    return "en"


def init(_plugin=None) -> None:
    """Detect the system language and merge locale files when present."""
    global _current
    _current = _detect_locale()
    try:
        from core import l10n

        overrides = l10n.load(_current)
        if overrides:
            _STRINGS.setdefault(_current, {}).update(overrides)
            if _current != "en":
                _STRINGS.setdefault("en", {}).update(
                    {key: value for key, value in overrides.items() if key not in _STRINGS["en"]}
                )
    except Exception:
        pass


def set_locale(code: str) -> None:
    global _current
    code = (code or "").replace("-", "_").split("_")[0].lower()
    _current = code if code in _STRINGS else "en"


def locale() -> str:
    return _current


def t(key: str, **kwargs: Any) -> str:
    """Translate ``key`` and format named placeholders."""
    value: Optional[str] = _STRINGS.get(_current, {}).get(key)
    if value is None:
        value = _STRINGS["en"].get(key)
    if value is None:
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value
