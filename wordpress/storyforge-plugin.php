<?php
/**
 * Plugin Name: StoryForge Bot
 * Description: Endpoints REST para el bot de Telegram StoryForge
 * Version: 1.2.0
 * Author: StoryForge
 */

if (!defined('ABSPATH')) exit;

define('STORYFORGE_VERSION', '1.2.0');

// Actualizar tabla si la versión del plugin cambió
add_action('plugins_loaded', 'storyforge_maybe_upgrade');
register_activation_hook(__FILE__, 'storyforge_create_table');

function storyforge_maybe_upgrade() {
    if (get_option('storyforge_version') !== STORYFORGE_VERSION) {
        storyforge_create_table();
        update_option('storyforge_version', STORYFORGE_VERSION);
    }
}

function storyforge_create_table() {
    global $wpdb;
    $table   = $wpdb->prefix . 'storyforge_players';
    $charset = $wpdb->get_charset_collate();

    // dbDelta agrega columnas nuevas sin borrar las existentes
    $sql = "CREATE TABLE $table (
        id              bigint(20)   NOT NULL AUTO_INCREMENT,
        telegram_id     bigint(20)   NOT NULL,
        name            varchar(100) NOT NULL,
        theme           varchar(50)  NOT NULL DEFAULT 'fantasy',
        custom_theme    text,
        text_length     varchar(20)  NOT NULL DEFAULT 'normal',
        level           int(11)      NOT NULL DEFAULT 1,
        experience      int(11)      NOT NULL DEFAULT 0,
        story_summary   longtext,
        current_chapter varchar(100) DEFAULT 'inicio',
        inventory       longtext,
        created_at      datetime     DEFAULT CURRENT_TIMESTAMP,
        updated_at      datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY  (id),
        UNIQUE KEY   telegram_id (telegram_id)
    ) $charset;";

    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    dbDelta($sql);
}

add_action('rest_api_init', 'storyforge_register_routes');

function storyforge_register_routes() {
    register_rest_route('storyforge/v1', '/player/(?P<telegram_id>\d+)', [
        [
            'methods'             => 'GET',
            'callback'            => 'storyforge_get_player',
            'permission_callback' => 'storyforge_check_auth',
            'args'                => ['telegram_id' => ['required' => true, 'type' => 'integer']],
        ],
        [
            'methods'             => 'PUT',
            'callback'            => 'storyforge_update_player',
            'permission_callback' => 'storyforge_check_auth',
        ],
        [
            'methods'             => 'DELETE',
            'callback'            => 'storyforge_delete_player',
            'permission_callback' => 'storyforge_check_auth',
        ],
    ]);

    register_rest_route('storyforge/v1', '/player', [
        'methods'             => 'POST',
        'callback'            => 'storyforge_create_player',
        'permission_callback' => 'storyforge_check_auth',
    ]);
}

function storyforge_check_auth() {
    return current_user_can('manage_options');
}

function storyforge_get_player(WP_REST_Request $request) {
    global $wpdb;
    $table      = $wpdb->prefix . 'storyforge_players';
    $telegram_id = (int) $request['telegram_id'];

    $player = $wpdb->get_row(
        $wpdb->prepare("SELECT * FROM $table WHERE telegram_id = %d", $telegram_id),
        ARRAY_A
    );

    if (!$player) {
        return new WP_Error('not_found', 'Jugador no encontrado', ['status' => 404]);
    }

    $player['inventory'] = json_decode($player['inventory'] ?? '[]', true) ?: [];

    return rest_ensure_response($player);
}

function storyforge_create_player(WP_REST_Request $request) {
    global $wpdb;
    $table = $wpdb->prefix . 'storyforge_players';
    $data  = $request->get_json_params();

    if (empty($data['telegram_id']) || empty($data['name'])) {
        return new WP_Error('missing_fields', 'telegram_id y name son requeridos', ['status' => 400]);
    }

    $result = $wpdb->insert($table, [
        'telegram_id'     => (int) $data['telegram_id'],
        'name'            => sanitize_text_field($data['name']),
        'theme'           => sanitize_text_field($data['theme'] ?? 'fantasy'),
        'custom_theme'    => sanitize_textarea_field($data['custom_theme'] ?? ''),
        'text_length'     => sanitize_text_field($data['text_length'] ?? 'normal'),
        'level'           => 1,
        'experience'      => 0,
        'story_summary'   => '',
        'current_chapter' => 'inicio',
        'inventory'       => json_encode($data['inventory'] ?? []),
    ]);

    if ($result === false) {
        return new WP_Error('db_error', 'Error al crear el jugador: ' . $wpdb->last_error, ['status' => 500]);
    }

    return rest_ensure_response(['success' => true, 'id' => $wpdb->insert_id]);
}

function storyforge_update_player(WP_REST_Request $request) {
    global $wpdb;
    $table      = $wpdb->prefix . 'storyforge_players';
    $telegram_id = (int) $request['telegram_id'];
    $data       = $request->get_json_params();

    $allowed = ['level', 'experience', 'story_summary', 'current_chapter', 'inventory', 'text_length'];
    $update  = [];

    foreach ($allowed as $field) {
        if (!isset($data[$field])) continue;
        if ($field === 'inventory') {
            $update[$field] = json_encode($data[$field]);
        } elseif (in_array($field, ['level', 'experience'])) {
            $update[$field] = (int) $data[$field];
        } else {
            $update[$field] = $data[$field];
        }
    }

    if (empty($update)) {
        return new WP_Error('no_fields', 'No hay campos para actualizar', ['status' => 400]);
    }

    $result = $wpdb->update($table, $update, ['telegram_id' => $telegram_id]);

    if ($result === false) {
        return new WP_Error('db_error', 'Error al actualizar: ' . $wpdb->last_error, ['status' => 500]);
    }

    return rest_ensure_response(['success' => true]);
}

function storyforge_delete_player(WP_REST_Request $request) {
    global $wpdb;
    $table      = $wpdb->prefix . 'storyforge_players';
    $telegram_id = (int) $request['telegram_id'];

    $result = $wpdb->delete($table, ['telegram_id' => $telegram_id]);

    if ($result === false) {
        return new WP_Error('db_error', 'Error al eliminar: ' . $wpdb->last_error, ['status' => 500]);
    }

    return rest_ensure_response(['success' => true]);
}
