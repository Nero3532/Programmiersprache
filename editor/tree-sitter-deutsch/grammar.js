/**
 * tree-sitter-Grammatik für die Programmiersprache Deutsch.
 *
 * Zweck ist Werkzeugunterstützung: Syntaxhervorhebung, Faltung, Navigation.
 * Die verbindliche Syntaxprüfung macht weiterhin deutsch/parser.py über den
 * Language Server – diese Grammatik ist bewusst etwas großzügiger (sie kennt
 * keine Zeilenenden als Trennzeichen), damit sie ohne externen Scanner auskommt.
 */

const PREC = {
  ternaer: 1,
  oder: 2,
  und: 3,
  vergleich: 4,
  additiv: 5,
  multiplikativ: 6,
  unaer: 7,
  potenz: 8,
  aufruf: 9,
};

// Buchstaben inklusive Umlaute und ß (der Lexer akzeptiert jeden Unicode-Buchstaben)
const BUCHSTABE = /[a-zA-ZÀ-ÖØ-öø-ÿ_]/;
const BUCHSTABE_ZIFFER = /[a-zA-Z0-9À-ÖØ-öø-ÿ_]/;

module.exports = grammar({
  name: 'deutsch',

  extras: $ => [/\s/, $.kommentar],

  word: $ => $.bezeichner,

  // Ein 'wenn' nach einem vollstaendigen Ausdruck ist mehrdeutig: es kann den
  // Ternaer fortsetzen oder eine neue Anweisung beginnen. Beide Lesarten werden
  // verfolgt; die falsche scheitert kurz darauf am fehlenden 'sonst' bzw. Block.
  conflicts: $ => [
    [$.ausdrucks_anweisung, $.ternaer_ausdruck],
    [$.variable_deklaration, $.ternaer_ausdruck],
    [$.konstanten_deklaration, $.ternaer_ausdruck],
    [$.destrukturierende_deklaration, $.ternaer_ausdruck],
    [$.zuweisung, $.ternaer_ausdruck],
    [$.verbund_zuweisung, $.ternaer_ausdruck],
    [$.werfe_anweisung, $.ternaer_ausdruck],
  ],

  rules: {
    quelldatei: $ => repeat($._anweisung),

    kommentar: $ => token(seq('#', /[^\n]*/)),

    // ------------------------------------------------------------ Anweisungen

    _anweisung: $ => choice(
      $.variable_deklaration,
      $.konstanten_deklaration,
      $.destrukturierende_deklaration,
      $.funktion_definition,
      $.klassen_definition,
      $.wenn_anweisung,
      $.solange_anweisung,
      $.fuer_anweisung,
      $.passe_anweisung,
      $.versuche_anweisung,
      $.zurueck_anweisung,
      $.werfe_anweisung,
      $.pruefe_anweisung,
      $.lade_anweisung,
      $.abbrechen_anweisung,
      $.weiter_anweisung,
      $.zuweisung,
      $.verbund_zuweisung,
      $.ausdrucks_anweisung,
      ';',
    ),

    block: $ => seq('{', repeat($._anweisung), '}'),

    variable_deklaration: $ => seq(
      'sei',
      field('name', $.bezeichner),
      optional(seq(':', field('typ', $.typ_hinweis))),
      '=',
      field('wert', $._ausdruck),
    ),

    konstanten_deklaration: $ => seq(
      'konstante',
      field('name', $.bezeichner),
      optional(seq(':', field('typ', $.typ_hinweis))),
      '=',
      field('wert', $._ausdruck),
    ),

    destrukturierende_deklaration: $ => seq(
      'sei',
      $.namensliste,
      '=',
      field('wert', $._ausdruck),
    ),

    namensliste: $ => seq('[', commaSep1($.bezeichner), ']'),

    typ_hinweis: $ => $.bezeichner,

    parameter: $ => seq(
      optional('*'),
      field('name', $.bezeichner),
      optional(seq(':', field('typ', $.typ_hinweis))),
      optional(seq('=', field('standard', $._ausdruck))),
    ),

    parameterliste: $ => seq('(', optional(commaSep1($.parameter)), ')'),

    funktion_definition: $ => prec(1, seq(
      'funktion',
      field('name', $.bezeichner),
      field('parameter', $.parameterliste),
      optional(seq('->', field('rueckgabetyp', $.typ_hinweis))),
      field('koerper', $.block),
    )),

    statische_methode: $ => seq('statisch', $.funktion_definition),

    klassen_definition: $ => seq(
      'klasse',
      field('name', $.bezeichner),
      optional(seq('(', commaSep1(field('eltern', $.bezeichner)), ')')),
      field('koerper', $.klassen_koerper),
    ),

    klassen_koerper: $ => seq('{', repeat(choice(
      $.funktion_definition,
      $.statische_methode,
      $.variable_deklaration,
      $.konstanten_deklaration,
      ';',
    )), '}'),

    wenn_anweisung: $ => prec.right(seq(
      'wenn',
      field('bedingung', $._ausdruck),
      field('dann', $.block),
      repeat($.sonst_wenn_zweig),
      optional($.sonst_zweig),
    )),

    sonst_wenn_zweig: $ => seq(
      'sonst', 'wenn',
      field('bedingung', $._ausdruck),
      field('dann', $.block),
    ),

    sonst_zweig: $ => seq('sonst', field('sonst', $.block)),

    solange_anweisung: $ => seq(
      'solange',
      field('bedingung', $._ausdruck),
      field('koerper', $.block),
    ),

    fuer_anweisung: $ => seq(
      choice('für', 'fuer'),
      field('variable', choice($.bezeichner, $.namensliste)),
      'in',
      field('iterable', $._ausdruck),
      field('koerper', $.block),
    ),

    passe_anweisung: $ => seq(
      'passe',
      field('wert', $._ausdruck),
      '{',
      repeat(choice($.fall_zweig, $.passe_sonst_zweig)),
      '}',
    ),

    fall_zweig: $ => seq('fall', commaSep1($._ausdruck), ':', $.block),

    passe_sonst_zweig: $ => seq('sonst', ':', $.block),

    versuche_anweisung: $ => seq(
      'versuche',
      field('koerper', $.block),
      optional($.fange_zweig),
      optional($.endlich_zweig),
    ),

    fange_zweig: $ => seq(
      'fange',
      optional(seq('(', commaSep1(field('fehlertyp', $.bezeichner)), ')')),
      optional(field('name', $.bezeichner)),
      $.block,
    ),

    endlich_zweig: $ => seq('endlich', $.block),

    zurueck_anweisung: $ => prec.right(seq(
      choice('zurück', 'zurueck'),
      optional($._ausdruck),
    )),

    werfe_anweisung: $ => seq('werfe', $._ausdruck),

    pruefe_anweisung: $ => prec.right(seq(
      'pruefe',
      field('bedingung', $._ausdruck),
      optional(seq(',', field('meldung', $._ausdruck))),
    )),

    lade_anweisung: $ => prec.right(seq(
      'lade',
      field('pfad', $._ausdruck),
      optional(seq('als', field('name', $.bezeichner))),
    )),

    abbrechen_anweisung: $ => 'abbrechen',
    weiter_anweisung: $ => 'weiter',

    zuweisung: $ => seq(
      field('ziel', $._zuweisungsziel),
      '=',
      field('wert', $._ausdruck),
    ),

    verbund_zuweisung: $ => seq(
      field('ziel', $._zuweisungsziel),
      field('operator', choice('+=', '-=', '*=', '/=', '%=', '**=', '//=')),
      field('wert', $._ausdruck),
    ),

    _zuweisungsziel: $ => choice($.bezeichner, $.attribut_zugriff, $.index_zugriff),

    ausdrucks_anweisung: $ => $._ausdruck,

    // ------------------------------------------------------------- Ausdrücke

    _ausdruck: $ => choice(
      $.ternaer_ausdruck,
      $.binaere_operation,
      $.unaere_operation,
      $.aufruf,
      $.attribut_zugriff,
      $.index_zugriff,
      $.neu_ausdruck,
      $.funktion_ausdruck,
      $.klammer_ausdruck,
      $.liste,
      $.listen_abstraktion,
      $.woerterbuch,
      $.woerterbuch_abstraktion,
      $.menge,
      $.mengen_abstraktion,
      $._literal,
      $.bezeichner,
    ),

    klammer_ausdruck: $ => seq('(', $._ausdruck, ')'),

    // Ohne statische Vorrangregel: nach einem Ausdruck kann 'wenn' den Ternaer
    // fortsetzen ODER eine neue Anweisung beginnen (die Grammatik kennt keine
    // Zeilenenden). Der Konflikt wird deklariert, damit GLR beide Lesarten
    // verfolgt – die falsche stirbt am fehlenden 'sonst' beziehungsweise am Block.
    ternaer_ausdruck: $ => prec.right(seq(
      field('dann', $._ausdruck),
      'wenn',
      field('bedingung', $._ausdruck),
      'sonst',
      field('sonst', $._ausdruck),
    )),

    binaere_operation: $ => choice(
      ...[
        ['oder', PREC.oder], ['und', PREC.und],
        ['+', PREC.additiv], ['-', PREC.additiv],
        ['*', PREC.multiplikativ], ['/', PREC.multiplikativ],
        ['//', PREC.multiplikativ], ['%', PREC.multiplikativ],
      ].map(([operator, p]) => prec.left(p, seq(
        field('links', $._ausdruck),
        field('operator', operator),
        field('rechts', $._ausdruck),
      ))),
      ...[
        '==', '!=', '<', '>', '<=', '>=', 'in',
      ].map(operator => prec.left(PREC.vergleich, seq(
        field('links', $._ausdruck),
        field('operator', operator),
        field('rechts', $._ausdruck),
      ))),
      prec.left(PREC.vergleich, seq(
        field('links', $._ausdruck),
        field('operator', alias(seq('nicht', 'in'), $.nicht_in)),
        field('rechts', $._ausdruck),
      )),
      prec.right(PREC.potenz, seq(
        field('links', $._ausdruck),
        field('operator', '**'),
        field('rechts', $._ausdruck),
      )),
    ),

    unaere_operation: $ => prec.right(PREC.unaer, seq(
      field('operator', choice('nicht', '-')),
      field('operand', $._ausdruck),
    )),

    argument: $ => choice(
      $._ausdruck,
      $.entpacktes_argument,
      seq(field('name', $.bezeichner), '=', field('wert', $._ausdruck)),
    ),

    // f(*folge) – nur an Aufrufstellen, deshalb kein Konflikt mit der Multiplikation
    entpacktes_argument: $ => seq('*', field('ausdruck', $._ausdruck)),

    argumentliste: $ => seq('(', optional(commaSep1($.argument)), ')'),

    aufruf: $ => prec(PREC.aufruf, seq(
      field('funktion', $._ausdruck),
      field('argumente', $.argumentliste),
    )),

    attribut_zugriff: $ => prec(PREC.aufruf, seq(
      field('objekt', $._ausdruck),
      '.',
      field('attribut', $.bezeichner),
    )),

    index_zugriff: $ => prec(PREC.aufruf, seq(
      field('objekt', $._ausdruck),
      '[',
      field('index', choice($._ausdruck, $.schnitt)),
      ']',
    )),

    schnitt: $ => choice(
      seq(optional($._ausdruck), ':', optional($._ausdruck)),
      seq(optional($._ausdruck), ':', optional($._ausdruck), ':', optional($._ausdruck)),
    ),

    // Wie im Parser: nur ein gepunkteter Bezeichnerpfad, kein beliebiger Ausdruck
    neu_ausdruck: $ => seq(
      'neu',
      field('klasse', $.klassen_pfad),
      field('argumente', $.argumentliste),
    ),

    klassen_pfad: $ => seq($.bezeichner, repeat(seq('.', $.bezeichner))),

    funktion_ausdruck: $ => seq(
      'funktion',
      optional(field('name', $.bezeichner)),
      field('parameter', $.parameterliste),
      optional(seq('->', field('rueckgabetyp', $.typ_hinweis))),
      field('koerper', $.block),
    ),

    liste: $ => seq('[', optional(seq(commaSep1($._ausdruck), optional(','))), ']'),

    // Eine Klausel je verschachtelter Schleife; die spaetere sieht die Variablen
    // der frueheren.
    abstraktions_klausel: $ => seq(
      choice('für', 'fuer'),
      field('variable', choice($.bezeichner, $.namensliste)),
      'in',
      field('iterable', $._ausdruck),
      optional(seq('wenn', field('bedingung', $._ausdruck))),
    ),

    listen_abstraktion: $ => seq(
      '[',
      field('ausdruck', $._ausdruck),
      repeat1($.abstraktions_klausel),
      ']',
    ),

    mengen_abstraktion: $ => seq(
      '{',
      field('ausdruck', $._ausdruck),
      repeat1($.abstraktions_klausel),
      '}',
    ),

    woerterbuch_abstraktion: $ => seq(
      '{',
      field('schluessel', $._ausdruck),
      ':',
      field('wert', $._ausdruck),
      repeat1($.abstraktions_klausel),
      '}',
    ),

    paar: $ => seq(field('schluessel', $._ausdruck), ':', field('wert', $._ausdruck)),

    woerterbuch: $ => seq('{', optional(seq(commaSep1($.paar), optional(','))), '}'),

    menge: $ => seq('{', commaSep1($._ausdruck), optional(','), '}'),

    // --------------------------------------------------------------- Literale

    _literal: $ => choice(
      $.ganzzahl,
      $.kommazahl,
      $.zeichenkette,
      $.wahrheitswert,
      $.nichts,
    ),

    ganzzahl: $ => token(/\d+/),

    kommazahl: $ => token(choice(
      /\d+\.\d+([eE][+-]?\d+)?/,
      /\d+[eE][+-]?\d+/,
    )),

    wahrheitswert: $ => choice('wahr', 'falsch'),
    nichts: $ => 'nichts',

    zeichenkette: $ => choice(
      $._roher_dreifach_string,
      seq('"', repeat(choice($._text_doppelt, $.escape, $.interpolation)), '"'),
      seq("'", repeat(choice($._text_einfach, $.escape, $.interpolation)), "'"),
    ),

    // Dreifach gequotet: ein einzelnes Token, Interpolation wird hier nicht
    // aufgeschlüsselt (die Fälle sind selten und der Aufwand im DFA hoch).
    _roher_dreifach_string: $ => token(choice(
      seq('"""', repeat(choice(/[^"]/, /"[^"]/, /""[^"]/)), '"""'),
      seq("'''", repeat(choice(/[^']/, /'[^']/, /''[^']/)), "'''"),
    )),

    _text_doppelt: $ => token.immediate(prec(1, /[^"\\{}\n]+/)),
    _text_einfach: $ => token.immediate(prec(1, /[^'\\{}\n]+/)),

    escape: $ => token.immediate(seq('\\', /./)),

    interpolation: $ => seq(
      '{',
      field('ausdruck', $._ausdruck),
      optional(seq(':', field('format', $.format_spezifizierer))),
      '}',
    ),

    format_spezifizierer: $ => token(/[^{}"']+/),

    bezeichner: $ => token(seq(BUCHSTABE, repeat(BUCHSTABE_ZIFFER))),
  },
});

function commaSep1(regel) {
  return seq(regel, repeat(seq(',', regel)));
}
