<?php
/**
 * Plugin Name: Fitness Timer App
 * Description: Provides a configurable fitness timer with stopwatch, countdown, and interval presets.
 * Version: 1.0.0
 * Author: Fitness Trainer App Team
 * License: GPL2
 * Requires at least: 5.8
 * Requires PHP: 5.6
 */

if (!defined('ABSPATH')) {
    exit;
}

class Fitness_Timer_App {
    private static $instance = null;

    public static function get_instance() {
        if (self::$instance === null) {
            self::$instance = new self();
        }

        return self::$instance;
    }

    private function __construct() {
        add_action('init', [$this, 'register_shortcodes']);
        add_action('wp_enqueue_scripts', [$this, 'register_assets']);
    }

    public function register_assets() {
        $plugin_url = plugin_dir_url(__FILE__);
        $version = '1.0.0';

        wp_register_style(
            'fitness-timer-app',
            $plugin_url . 'assets/css/timer-app.css',
            [],
            $version
        );

        wp_register_script(
            'fitness-timer-app',
            $plugin_url . 'assets/js/timer-app.js',
            [],
            $version,
            true
        );
    }

    public function register_shortcodes() {
        add_shortcode('fitness_timer', [$this, 'render_timer_shortcode']);
    }

    public function render_timer_shortcode($atts) {
        $atts = shortcode_atts(
            [
                'mode' => 'stopwatch',
                'duration' => 60,
                'intervals' => '',
                'title' => 'Training Timer',
                'show_notes' => 'true',
            ],
            $atts,
            'fitness_timer'
        );

        wp_enqueue_style('fitness-timer-app');
        wp_enqueue_script('fitness-timer-app');

        $intervals = $this->parse_intervals($atts['intervals']);

        $data = esc_attr(wp_json_encode([
            'mode' => sanitize_text_field($atts['mode']),
            'duration' => (int) $atts['duration'],
            'intervals' => $intervals,
            'showNotes' => filter_var($atts['show_notes'], FILTER_VALIDATE_BOOLEAN),
        ]));

        ob_start();
        ?>
        <div class="fitness-timer" data-config="<?php echo $data; ?>">
            <div class="fitness-timer__header">
                <h3 class="fitness-timer__title"><?php echo esc_html($atts['title']); ?></h3>
                <div class="fitness-timer__mode" role="status" aria-live="polite"></div>
            </div>
            <div class="fitness-timer__display" aria-live="assertive">00:00</div>
            <div class="fitness-timer__controls">
                <button type="button" class="fitness-timer__btn fitness-timer__btn--start">Start</button>
                <button type="button" class="fitness-timer__btn fitness-timer__btn--pause" disabled>Pause</button>
                <button type="button" class="fitness-timer__btn fitness-timer__btn--reset" disabled>Reset</button>
                <button type="button" class="fitness-timer__btn fitness-timer__btn--lap" disabled>Lap</button>
            </div>
            <div class="fitness-timer__intervals"></div>
            <ul class="fitness-timer__laps" aria-live="polite"></ul>
            <?php if (filter_var($atts['show_notes'], FILTER_VALIDATE_BOOLEAN)) : ?>
                <label class="fitness-timer__notes">
                    <span>Notes</span>
                    <textarea placeholder="Add reminders or cues for your workout."></textarea>
                </label>
            <?php endif; ?>
        </div>
        <?php
        return ob_get_clean();
    }

    private function parse_intervals($intervals) {
        if (empty($intervals)) {
            return [];
        }

        $entries = array_map('trim', explode(',', $intervals));
        $parsed = [];

        foreach ($entries as $entry) {
            if (strpos($entry, ':') === false) {
                continue;
            }

            $parts = array_map('trim', explode(':', $entry, 2));
            if (count($parts) < 2) {
                continue;
            }

            list($label, $seconds) = $parts;
            $seconds = (int) $seconds;

            if ($seconds <= 0) {
                continue;
            }

            $parsed[] = [
                'label' => sanitize_text_field($label),
                'duration' => $seconds,
            ];
        }

        return $parsed;
    }
}

Fitness_Timer_App::get_instance();
