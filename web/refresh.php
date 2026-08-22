<?php
// Déclenché par le bouton "SYNCHRONISER" du dashboard. Lance le pipeline complet
// (scrape -> analyse -> génération) et renvoie un statut exploitable par le JS.
// À placer dans le document root du serveur web (ex: /var/www/html/refresh.php).

// Adapter si le nom d'utilisateur/chemin du dépôt diffère.
$appDir = '/home/dietpi/strava_export';

header('Content-Type: application/json');

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
