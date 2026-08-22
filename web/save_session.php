<?php
// Reçoit cookies + csrf-token depuis le bookmarklet (cliqué depuis strava.com, une fois
// connecté normalement) et les écrit au format que fetch_scraper.py sait relire.
// Aucune automatisation du login Strava : uniquement un humain qui clique. À placer dans
// le document root du serveur web (ex: /var/www/html/save_session.php).

$appDir = '/opt/strava_export';
$secretFile = "$appDir/output/.session_secret";
$sessionFile = "$appDir/output/strava_session.json";

header('Access-Control-Allow-Origin: https://www.strava.com');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

header('Content-Type: application/json');

if (!file_exists($secretFile)) {
    echo json_encode(['success' => false, 'message' => 'Secret non configuré sur le serveur']);
    exit;
}

$expected = trim(file_get_contents($secretFile));
$provided = $_GET['token'] ?? '';

if ($expected === '' || !hash_equals($expected, $provided)) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Token invalide']);
    exit;
}

$body = json_decode(file_get_contents('php://input'), true);
if (!$body || empty($body['cookies']) || empty($body['csrf_token'])) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => 'Payload invalide']);
    exit;
}

$data = ['cookies' => $body['cookies'], 'csrf_token' => $body['csrf_token']];

if (file_put_contents($sessionFile, json_encode($data)) === false) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => "Écriture impossible dans $sessionFile (permissions ?)"]);
    exit;
}

echo json_encode(['success' => true]);
