"""Settings pages.

Every page is built from the same primitives, reads live values through
:class:`core.prefs.Prefs` and reuses the plugin callbacks. Numbers are entered as
text, so each numeric row validates and clamps on change instead of trusting the
input widget.
"""

from __future__ import annotations

import os
from typing import Any, Callable, List, Optional

from core import assets, colors, files, javabridge, prefs, state, theme
from i18n import locale, t
from skins import registry as skins_registry
from themes import model as themes_model
from ayu_ui import compose
from ayu_ui.bulletin import bulletin_error, bulletin_info, dialog_choose, dialog_message

KIND_LABELS = (
    (prefs.KIND_GRADIENT, "kind_gradient"),
    (prefs.KIND_PARALLAX, "kind_parallax"),
    (prefs.KIND_PARTICLES, "kind_particles"),
    (prefs.KIND_VIDEO, "kind_video"),
)

SOURCE_LABELS = (
    (prefs.SOURCE_BUILTIN, "source_builtin"),
    (prefs.SOURCE_FILE, "source_file"),
    (prefs.SOURCE_URL, "source_url"),
)

PARTICLE_LABELS = (
    (prefs.PARTICLES_SNOW, "particles_snow"),
    (prefs.PARTICLES_STARS, "particles_stars"),
    (prefs.PARTICLES_BUBBLES, "particles_bubbles"),
    (prefs.PARTICLES_RAIN, "particles_rain"),
)

SKIN_MODE_LABELS = (
    (prefs.SKIN_AUTO, "skins_mode_auto"),
    (prefs.SKIN_TINT, "skins_mode_tint"),
    (prefs.SKIN_TEXTURE, "skins_mode_texture"),
)


def _index_of(options, value: str) -> int:
    for index, (key, _label) in enumerate(options):
        if key == value:
            return index
    return 0


def _value_of(options, index: Any, fallback: str) -> str:
    try:
        position = int(index)
    except (TypeError, ValueError):
        return fallback
    if 0 <= position < len(options):
        return options[position][0]
    return fallback


class Pages:
    """Builds every settings page. Holds the plugin for callbacks."""

    def __init__(self, plugin: Any) -> None:
        self.plugin = plugin
        self.prefs = plugin.prefs

    # ------------------------------------------------------------------ A1
    def page_wallpaper(self) -> List[Any]:
        plugin = self.plugin
        rows: List[Any] = [compose.header(t("header_wallpaper"))]

        rows.append(
            compose.switch(
                "wallpaper_enabled",
                t("wallpaper_enabled"),
                self.prefs.bool("wallpaper_enabled"),
                t("wallpaper_enabled_sub"),
                on_change=lambda _value: plugin.on_wallpaper_changed(),
            )
        )

        rows.append(
            compose.selector(
                "wallpaper_kind",
                t("wallpaper_kind"),
                _index_of(KIND_LABELS, self.prefs.text("wallpaper_kind")),
                [t(label) for _key, label in KIND_LABELS],
                t("wallpaper_kind_sub"),
                on_change=lambda index: self._set_kind(index),
            )
        )

        rows.append(compose.divider(t("wallpaper_source")))
        rows.append(
            compose.selector(
                "wallpaper_source",
                t("wallpaper_source"),
                _index_of(SOURCE_LABELS, self.prefs.text("wallpaper_source")),
                [t(label) for _key, label in SOURCE_LABELS],
                t("wallpaper_source_sub"),
                on_change=lambda index: self._set_source(index),
            )
        )

        builtin_names = assets.BUILTIN_NAMES
        rows.append(
            compose.selector(
                "wallpaper_builtin",
                t("wallpaper_builtin"),
                self._builtin_index(builtin_names),
                builtin_names,
                None,
                on_change=lambda _index: plugin.on_wallpaper_changed(),
            )
        )

        rows.append(
            compose.action(
                t("wallpaper_reload"),
                t("wallpaper_reload_sub"),
                icon="msg_retry",
                on_click=lambda _view: plugin.reload_background(),
            )
        )
        rows.append(
            compose.text_input(
                "wallpaper_url",
                t("wallpaper_url"),
                self.prefs.text("wallpaper_url"),
                t("wallpaper_url_sub"),
                on_change=lambda value: plugin.on_url_entered(value),
            )
        )

        rows.append(
            compose.action(
                t("wallpaper_pick_file"),
                t("wallpaper_pick_file_sub"),
                icon="msg_photos",
                on_click=lambda _view: plugin.pick_background_file(),
            )
        )

        rows.append(
            compose.info(
                t("wallpaper_current"),
                self._source_summary(),
                icon="msg_info",
            )
        )

        rows.append(compose.divider())
        rows.append(compose.header(t("header_look")))

        rows.append(self._number_row("wallpaper_dim", t("wallpaper_dim"), t("wallpaper_dim_sub")))
        rows.append(self._number_row("wallpaper_tint", t("wallpaper_tint"), t("wallpaper_tint_sub")))
        rows.append(self._number_row("wallpaper_blur", t("wallpaper_blur"), t("wallpaper_blur_sub")))
        rows.append(self._number_row("wallpaper_speed", t("wallpaper_speed"), t("wallpaper_speed_sub")))
        rows.append(self._number_row("wallpaper_scale", t("wallpaper_scale"), t("wallpaper_scale_sub")))
        rows.append(self._number_row("wallpaper_offset_x", t("wallpaper_offset_x"), None))
        rows.append(self._number_row("wallpaper_offset_y", t("wallpaper_offset_y"), None))

        rows.append(
            compose.switch(
                "wallpaper_fade",
                t("wallpaper_fade"),
                self.prefs.bool("wallpaper_fade"),
                t("wallpaper_fade_sub"),
                on_change=lambda _value: plugin.on_wallpaper_changed(),
            )
        )
        rows.append(
            self._number_row(
                "wallpaper_fade_duration",
                t("wallpaper_fade_duration"),
                t("wallpaper_fade_duration_sub"),
            )
        )

        rows.append(compose.divider())
        rows.append(
            compose.switch(
                "wallpaper_apply_chat",
                t("wallpaper_apply_chat"),
                self.prefs.bool("wallpaper_apply_chat"),
                None,
                on_change=lambda _value: plugin.on_wallpaper_changed(),
            )
        )
        rows.append(
            compose.switch(
                "wallpaper_apply_dialogs",
                t("wallpaper_apply_dialogs"),
                self.prefs.bool("wallpaper_apply_dialogs"),
                None,
                on_change=lambda _value: plugin.on_wallpaper_changed(),
            )
        )
        rows.append(
            compose.switch(
                "wallpaper_apply_everywhere",
                t("wallpaper_apply_everywhere"),
                self.prefs.bool("wallpaper_apply_everywhere"),
                t("wallpaper_apply_everywhere_sub"),
                on_change=lambda _value: plugin.on_wallpaper_changed(),
            )
        )
        rows.append(
            compose.action(
                t("header_particles"),
                None,
                icon="msg_settings",
                sub_page=self.page_particles,
            )
        )
        return rows

    # ------------------------------------------------------------------ A2
    def page_particles(self) -> List[Any]:
        plugin = self.plugin
        rows: List[Any] = [compose.header(t("header_particles"))]
        rows.append(
            compose.selector(
                "particles_type",
                t("particles_type"),
                _index_of(PARTICLE_LABELS, self.prefs.text("particles_type")),
                [t(label) for _key, label in PARTICLE_LABELS],
                t("particles_type_sub"),
                on_change=lambda index: self._set_particles_type(index),
            )
        )
        rows.append(self._number_row("particles_count", t("particles_count"), t("particles_count_sub")))
        rows.append(self._number_row("particles_size", t("particles_size"), None))
        rows.append(self._number_row("particles_speed", t("particles_speed"), None))
        rows.append(self._number_row("particles_alpha", t("particles_alpha"), None))
        rows.append(
            compose.text_input(
                "particles_color",
                t("particles_color"),
                self.prefs.text("particles_color"),
                t("particles_color_sub"),
                on_change=lambda value: self._set_color("particles_color", value),
            )
        )
        return rows

    # ------------------------------------------------------------------ B
    def page_themes(self) -> List[Any]:
        plugin = self.plugin
        themes = themes_model.load_all()
        rows: List[Any] = [compose.header(t("header_themes"))]

        if not themes:
            rows.append(compose.info(t("theme_list_empty"), t("theme_list_empty_sub")))
        else:
            names = [str(item.get("name")) for item in themes]
            active = self.prefs.text("theme_active")
            rows.append(
                compose.selector(
                    "theme_active_name",
                    t("theme_active"),
                    _index_of(tuple((name, name) for name in names), active),
                    names,
                    t("theme_active_sub"),
                    on_change=lambda index: plugin.apply_theme_by_index(index),
                )
            )
            for index, item in enumerate(themes):
                rows.append(
                    compose.action(
                        str(item.get("name")),
                        "%s · %s" % (item.get("accent"), item.get("created")),
                        icon="msg_colors",
                        on_click=(lambda _view, i=index: plugin.preview_theme(i)),
                    )
                )

        rows.append(compose.divider())
        rows.append(
            compose.action(
                t("theme_create"),
                None,
                icon="msg_add",
                on_click=lambda _view: plugin.create_theme_from_current(),
            )
        )
        rows.append(self._color_row("theme_accent", t("theme_accent"), t("theme_accent_sub")))
        rows.append(self._color_row("theme_out_bubble", t("theme_out_bubble"), None))
        rows.append(self._color_row("theme_in_bubble", t("theme_in_bubble"), None))
        rows.append(self._color_row("theme_header_color", t("theme_header_color"), None))
        rows.append(self._color_row("theme_page_color", t("theme_page_color"), None))
        rows.append(self._number_row("theme_bubbles_alpha", t("theme_bubbles_alpha"), None))

        rows.append(
            compose.action(
                t("theme_apply"),
                t("theme_apply_sub"),
                icon="msg_done",
                on_click=lambda _view: plugin.apply_current_theme(),
            )
        )
        rows.append(
            compose.action(
                t("theme_import"),
                t("theme_import_sub"),
                icon="msg_file",
                on_click=lambda _view: plugin.import_theme_archive(),
            )
        )
        rows.append(
            compose.action(
                t("theme_reset"),
                None,
                icon="msg_retry",
                on_click=lambda _view: plugin.reset_theme(),
            )
        )
        if themes:
            rows.append(
                compose.action(
                    t("theme_delete"),
                    None,
                    icon="msg_delete",
                    on_click=lambda _view: plugin.delete_active_theme(),
                )
            )
        return rows

    # ------------------------------------------------------------------ C
    def page_skins(self) -> List[Any]:
        plugin = self.plugin
        rows: List[Any] = [compose.header(t("header_skins"))]
        rows.append(
            compose.switch(
                "skins_enabled",
                t("skins_enabled"),
                self.prefs.bool("skins_enabled"),
                t("skins_enabled_sub"),
                on_change=lambda _value: plugin.apply_skins(),
            )
        )
        rows.append(
            compose.selector(
                "skins_mode",
                t("skins_mode"),
                _index_of(SKIN_MODE_LABELS, self.prefs.text("skins_mode")),
                [t(label) for _key, label in SKIN_MODE_LABELS],
                t("skins_mode_sub"),
                on_change=lambda _index: plugin.apply_skins(),
            )
        )

        folders = skins_registry.Registry().scan()
        if folders:
            rows.append(
                compose.selector(
                    "skin_active",
                    t("skin_active"),
                    max(0, _index_of(tuple((name, name) for name in folders), self.prefs.text("skin_active"))),
                    folders,
                    None,
                    on_change=lambda index: plugin.activate_skin(index, folders),
                )
            )
        else:
            rows.append(compose.info(t("skin_state_missing"), t("skin_import_hint")))

        rows.append(
            compose.action(
                t("skin_create"),
                t("skin_import_hint"),
                icon="msg_folder",
                on_click=lambda _view: plugin.create_default_skin(),
            )
        )
        rows.append(
            compose.action(
                t("skin_import"),
                t("skin_import_sub"),
                icon="msg_file",
                on_click=lambda _view: plugin.import_skin_archive(),
            )
        )
        rows.append(
            compose.action(
                t("skin_reload"),
                None,
                icon="msg_retry",
                on_click=lambda _view: plugin.apply_skins(force_reload=True),
            )
        )
        rows.append(
            compose.info(
                t("skin_state"),
                self._skin_summary(),
                icon="msg_info",
            )
        )
        rows.append(compose.divider())
        for element, label in (
            (skins_registry.ELEMENT_OUT, t("skin_element_out")),
            (skins_registry.ELEMENT_IN, t("skin_element_in")),
            (skins_registry.ELEMENT_PANEL, t("skin_element_panel")),
            (skins_registry.ELEMENT_HEADER, t("skin_element_header")),
        ):
            rows.append(compose.info(label, self._element_status(element)))
        return rows

    # ------------------------------------------------------------------ D
    def page_per_chat(self) -> List[Any]:
        plugin = self.plugin
        overrides = plugin.wallpaper.overrides
        rows: List[Any] = [compose.header(t("header_per_chat"))]
        items = overrides.items()
        rows.append(compose.info(t("per_chat_count", count=len(items))))
        if not items:
            rows.append(compose.info(t("per_chat_empty"), t("per_chat_empty_sub")))
        else:
            kind_labels = {key: t(label) for key, label in KIND_LABELS}
            for dialog_key, data in items:
                kind = str(data.get("kind") or self.prefs.text("wallpaper_kind"))
                rows.append(
                    compose.info(
                        "Чат %s" % dialog_key if locale().startswith("ru") else "Chat %s" % dialog_key,
                        "%s · %s" % (kind_labels.get(kind, kind), data.get("source", "")),
                        icon="msg_chat",
                    )
                )
                rows.append(
                    compose.action(
                        t("per_chat_reset_one"),
                        None,
                        icon="msg_delete",
                        on_click=(lambda _view, key=dialog_key: plugin.clear_chat_override(key)),
                    )
                )
            rows.append(
                compose.action(
                    t("per_chat_reset_all"),
                    None,
                    icon="msg_delete",
                    on_click=lambda _view: plugin.clear_all_chat_overrides(),
                )
            )
        return rows

    # ------------------------------------------------------------------ E
    def page_performance(self) -> List[Any]:
        plugin = self.plugin
        rows: List[Any] = [compose.header(t("header_perf_general"))]
        rows.append(
            compose.switch(
                "perf_eco",
                t("perf_eco"),
                self.prefs.bool("perf_eco"),
                t("perf_eco_sub"),
                on_change=lambda _value: plugin.apply_performance(),
            )
        )
        rows.append(self._number_row("perf_fps", t("perf_fps"), t("perf_fps_sub"), on_change=plugin.apply_performance))
        rows.append(self._number_row("perf_quality", t("perf_quality"), t("perf_quality_sub")))
        rows.append(
            compose.switch(
                "perf_pause_scroll",
                t("perf_pause_scroll"),
                self.prefs.bool("perf_pause_scroll"),
                None,
                on_change=lambda _value: plugin.apply_performance(),
            )
        )
        rows.append(
            compose.switch(
                "perf_pause_idle",
                t("perf_pause_idle"),
                self.prefs.bool("perf_pause_idle"),
                None,
                on_change=lambda _value: plugin.apply_performance(),
            )
        )
        rows.append(
            self._number_row(
                "perf_idle_delay",
                t("perf_pause_idle_delay"),
                t("perf_pause_idle_delay_sub"),
                on_change=plugin.apply_performance,
            )
        )
        rows.append(
            compose.switch(
                "perf_pause_background",
                t("perf_pause_background"),
                self.prefs.bool("perf_pause_background"),
                None,
                on_change=lambda _value: plugin.apply_performance(),
            )
        )
        rows.append(
            compose.action(
                t("header_particles"),
                None,
                icon="msg_settings",
                sub_page=self.page_particles,
            )
        )
        rows.append(
            compose.info(
                t("perf_active", state=t(self._state_key())),
                None,
                icon="msg_info",
            )
        )
        return rows

    # ------------------------------------------------------------------ F
    def page_diagnostics(self) -> List[Any]:
        plugin = self.plugin
        rows: List[Any] = [compose.header(t("diag_header_env"))]
        rows.append(compose.info(t("diag_client"), plugin.client_version()))
        rows.append(compose.info(t("diag_android"), "%s (SDK %d)" % (plugin.android_release(), javabridge.android_sdk())))
        rows.append(compose.info(t("diag_sdk"), plugin.plugin_sdk_version()))
        rows.append(compose.divider(t("diag_headers")))
        for name, bound in sorted(javabridge.bindings().items()):
            rows.append(
                compose.info(
                    name,
                    t("diag_hook_bound") if bound else t("diag_hook_missing"),
                    accent=bound,
                    red=not bound,
                )
            )
        rows.append(compose.info(t("diag_events_seen", count=state.hook_events)))
        last_error = state.last_error or ""
        rows.append(
            compose.info(
                t("diag_last_error", error=last_error) if last_error else t("diag_no_errors"),
                None,
                red=bool(last_error),
            )
        )
        rows.append(compose.divider())
        rows.append(
            compose.switch(
                "diag_debug",
                "Debug logs",
                self.prefs.bool("diag_debug"),
                "Verbose logcat output for plugin.custom_extra_ayu",
                on_change=lambda value: plugin.set_debug(value),
            )
        )
        rows.append(
            compose.action(
                t("diag_copy_log"),
                t("diag_copy_log_sub"),
                icon="msg_copy",
                on_click=lambda _view: plugin.copy_log(),
            )
        )
        rows.append(
            compose.action(
                t("diag_reset"),
                t("diag_reset_sub"),
                icon="msg_delete",
                on_click=lambda _view: plugin.reset_everything(),
            )
        )
        return rows

    # ------------------------------------------------------------------ rows
    def _number_row(self, key: str, text: str, subtext: Optional[str],
                    on_change: Optional[Callable] = None) -> Any:
        return compose.slider(
            key,
            text,
            self.prefs.int(key),
            subtext,
            on_change=lambda value: self._set_number(key, value, on_change),
        )

    def _color_row(self, key: str, text: str, subtext: Optional[str]) -> Any:
        return compose.text_input(
            key,
            text,
            self.prefs.text(key),
            subtext,
            on_change=lambda value: self._set_color(key, value),
        )

    # ------------------------------------------------------------------ setters
    def _set_number(self, key: str, value: Any, after: Optional[Callable] = None) -> None:
        try:
            number = prefs.clamp_int(key, str(value).strip())
        except Exception:
            return
        self.prefs.set(key, number)
        if key.startswith("wallpaper_") or key.startswith("particles_"):
            self.plugin.on_wallpaper_changed()
        if after is not None:
            try:
                after()
            except Exception:
                pass

    def _set_color(self, key: str, value: Any) -> None:
        parsed = colors.parse(str(value))
        if parsed is None:
            bulletin_error(t("theme_invalid_color"))
            return
        self.prefs.set(key, colors.to_hex(parsed))
        if key.startswith("theme_"):
            self.plugin.on_theme_changed()
        else:
            self.plugin.on_wallpaper_changed()

    def _set_kind(self, index: Any) -> None:
        value = _value_of(KIND_LABELS, index, prefs.KIND_GRADIENT)
        self.prefs.set("wallpaper_kind", value)
        self.plugin.on_wallpaper_changed()

    def _set_source(self, index: Any) -> None:
        value = _value_of(SOURCE_LABELS, index, prefs.SOURCE_BUILTIN)
        self.prefs.set("wallpaper_source", value)
        self.plugin.on_wallpaper_changed()

    def _set_particles_type(self, index: Any) -> None:
        value = _value_of(PARTICLE_LABELS, index, prefs.PARTICLES_SNOW)
        self.prefs.set("particles_type", value)
        self.plugin.on_wallpaper_changed()

    # ------------------------------------------------------------------ helpers
    def _builtin_index(self, names: List[str]) -> int:
        current = self.prefs.text("wallpaper_builtin")
        try:
            return names.index(current)
        except ValueError:
            return 0

    def _source_summary(self) -> str:
        service = self.plugin.wallpaper
        path = service.local_path()
        if path:
            size = files.file_size(path)
            return "%s · %.1f MB" % (service.describe_source(), size / (1024.0 * 1024.0))
        if service.last_error():
            return t("wallpaper_state_error", error=service.last_error())
        return t("wallpaper_missing")

    def _skin_summary(self) -> str:
        count = state.skin_elements
        if not count:
            return t("skin_state_missing")
        return t("skin_state_ok", count=count)

    def _element_status(self, element: str) -> str:
        skin = self.plugin.skins.current() if self.plugin.skins else None
        if skin is None:
            return t("off")
        if skin.has(element):
            return os.path.basename(skin.images.get(element, "")) or t("on")
        return t("off")

    def _state_key(self) -> str:
        if state.render_state == state.STATE_RUNNING:
            return "perf_state_running"
        if state.render_state == state.STATE_PAUSED:
            return "perf_state_paused"
        return "perf_state_off"
