<?php
// Déclenché par le bouton "SYNCHRONISER" du dashboard. Lance le pipeline complet
// (scrape -> analyse -> génération) et renvoie un statut exploitable par le JS.
// À placer dans le document root du serveur web (ex: /var/www/html/refresh.php).

$appDir = '/opt/strava_export';
$secretFile = "$appDir/output/.session_secret";

header('Content-Type: application/json');

// Même secret que save_session.php : ce endpoint est potentiellement exposé sur
// internet (port forwarding), il ne doit pas être déclenchable par n'importe qui.
if (!file_exists($secretFile)) {
    http_response_code(500);
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

$cmd = escapeshellcmd("$appDir/deploy/run_pipeline.sh") . ' 2>&1';
exec($cmd, $output, $exitCode);

if ($exitCode === 0) {
    echo json_encode(['success' => true]);
} elseif ($exitCode === 2) {
    // Code dédié renvoyé par fetch_scraper.py : session en cache absente/expirée.
    echo json_encode([
        'success' => false,
        'session_expired' => true,
        'message' => 'Session Strava expirée, reconnexion nécessaire.'
    ]);
} else {
    echo json_encode([
        'success' => false,
        'message' => implode("\n", array_slice($output, -10))
    ]);
}
