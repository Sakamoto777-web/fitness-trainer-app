# Fitness Timer App (WordPress Plugin)

A lightweight WordPress plugin that delivers a stopwatch, countdown, and interval training timer via the `[fitness_timer]` shortcode. Trainers can embed the widget into any post, page, or block to power HIIT sessions, AMRAP workouts, or general time tracking.

## Features

- **Multiple modes** – Switch between stopwatch, fixed countdown, or guided interval workouts.
- **Interval presets** – Pass interval definitions directly in the shortcode (e.g., warm-up, sprint, recover).
- **Lap tracking** – Capture lap times while the timer runs.
- **Workout notes** – Optional notes area for cues and reminders.
- **Responsive design** – Looks great on desktop and mobile.

## Installation

1. Download or clone this repository.
2. Compress the `wordpress-timer-app` directory into a ZIP file **or** copy the folder directly into your WordPress installation under `wp-content/plugins/` via FTP/SSH.
3. In the WordPress admin dashboard, either go to **Plugins → Add New → Upload Plugin** and upload the ZIP, or visit **Plugins → Installed Plugins** if you copied the folder manually.
4. Locate **Fitness Timer App** and click **Activate**.

## Usage

Embed the timer anywhere using the shortcode:

```text
[fitness_timer]
```

### Shortcode Options

| Attribute     | Type   | Default      | Description |
|---------------|--------|--------------|-------------|
| `mode`        | string | `stopwatch`  | Choose between `stopwatch`, `countdown`, or `interval`. |
| `duration`    | int    | `60`         | Length of the countdown (seconds). Used by `countdown` mode or as a fallback for intervals. |
| `intervals`   | string | `""`        | Comma-separated list of `label:seconds` pairs for interval mode. Example: `Warmup:120,Sprint:30,Rest:30`. |
| `title`       | string | `Training Timer` | Heading displayed at the top of the widget. |
| `show_notes`  | bool   | `true`       | Set to `false` to hide the notes textarea. |

### Examples

**Stopwatch with notes hidden**

```text
[fitness_timer title="Track Laps" mode="stopwatch" show_notes="false"]
```

**Countdown for AMRAP session**

```text
[fitness_timer title="12 Minute AMRAP" mode="countdown" duration="720"]
```

**HIIT intervals**

```text
[fitness_timer
    title="HIIT Sprints"
    mode="interval"
    intervals="Warmup:120,Sprint:45,Jog:30,Sprint:45,Cooldown:120"
]
```

Intervals appear in a checklist. The active interval is highlighted as the timer progresses.

## Development Notes

- Styles and scripts are only loaded when the shortcode renders on a page.
- JavaScript uses `requestAnimationFrame` for smooth timing updates.
- Lap entries are prepended so the most recent result appears first.

Feel free to extend the plugin with audio cues, saved presets, or Gutenberg block integration.
