// Erweiterung für die Programmiersprache Deutsch.
//
// Die Syntaxhervorhebung liefert VS Code selbst aus der TextMate-Grammatik;
// diese Datei verbindet den Editor mit dem Language Server (deutsch --lsp),
// der Fehleranzeige, Vervollständigung, Gliederung und Navigation beisteuert.

const { workspace, window, commands } = require('vscode');
const { LanguageClient, TransportKind } = require('vscode-languageclient/node');

let klient = null;

function einstellungen() {
  return workspace.getConfiguration('deutsch');
}

function serverOptionen() {
  const befehl = einstellungen().get('serverBefehl', ['deutsch', '--lsp']);
  if (!Array.isArray(befehl) || befehl.length === 0) {
    throw new Error("'deutsch.serverBefehl' muss eine nicht-leere Liste sein");
  }
  const lauf = {
    command: befehl[0],
    args: befehl.slice(1),
    transport: TransportKind.stdio,
    options: { cwd: arbeitsverzeichnis() },
  };
  return { run: lauf, debug: lauf };
}

function arbeitsverzeichnis() {
  const ordner = workspace.workspaceFolders;
  return ordner && ordner.length > 0 ? ordner[0].uri.fsPath : undefined;
}

async function starten() {
  if (klient) {
    return;
  }
  if (!einstellungen().get('sprachserverAktiv', true)) {
    return;
  }

  klient = new LanguageClient(
    'deutsch',
    'Deutsch Language Server',
    serverOptionen(),
    {
      documentSelector: [{ scheme: 'file', language: 'deutsch' }],
      synchronize: { fileEvents: workspace.createFileSystemWatcher('**/*.deu') },
      outputChannelName: 'Deutsch',
    },
  );

  try {
    await klient.start();
  } catch (fehler) {
    const befehl = einstellungen().get('serverBefehl', ['deutsch', '--lsp']).join(' ');
    klient = null;
    const auswahl = await window.showWarningMessage(
      `Der Language Server liess sich nicht starten (${befehl}). ` +
        'Syntaxhervorhebung funktioniert weiterhin, Fehleranzeige und ' +
        'Vervollstaendigung nicht.',
      'Einstellung oeffnen',
    );
    if (auswahl === 'Einstellung oeffnen') {
      commands.executeCommand('workbench.action.openSettings', 'deutsch.serverBefehl');
    }
  }
}

async function stoppen() {
  if (!klient) {
    return;
  }
  const alt = klient;
  klient = null;
  await alt.stop();
}

function activate(kontext) {
  kontext.subscriptions.push(
    workspace.onDidChangeConfiguration(async (ereignis) => {
      if (
        ereignis.affectsConfiguration('deutsch.serverBefehl') ||
        ereignis.affectsConfiguration('deutsch.sprachserverAktiv')
      ) {
        await stoppen();
        await starten();
      }
    }),
  );
  return starten();
}

function deactivate() {
  return stoppen();
}

module.exports = { activate, deactivate };
