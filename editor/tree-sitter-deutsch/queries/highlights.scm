; Syntaxhervorhebung für die Programmiersprache Deutsch

; ---------------------------------------------------------------- Kommentare
(kommentar) @comment

; ------------------------------------------------------------------ Literale
(ganzzahl) @number
(kommazahl) @number
(wahrheitswert) @boolean
(nichts) @constant.builtin

(zeichenkette) @string
(escape) @string.escape
(interpolation "{" @punctuation.special)
(interpolation "}" @punctuation.special)
(format_spezifizierer) @string.special

; ------------------------------------------------------------ Schlüsselwörter
[
  "sei"
  "konstante"
  "funktion"
  "klasse"
  "statisch"
  "neu"
  "lade"
  "als"
] @keyword

[
  "wenn"
  "sonst"
  "solange"
  "für"
  "fuer"
  "passe"
  "fall"
  "zurück"
  "zurueck"
  "ergibt"
] @keyword.control

; 'abbrechen' und 'weiter' sind Regeln aus einem einzigen String – tree-sitter
; macht daraus Blattknoten ohne anonymes Kind, sie werden benannt abgefragt.
[
  (abbrechen_anweisung)
  (weiter_anweisung)
] @keyword.control

[
  "versuche"
  "fange"
  "endlich"
  "werfe"
  "pruefe"
] @keyword.exception

[
  "und"
  "oder"
  "nicht"
  "in"
] @keyword.operator

; ------------------------------------------------------------------ Operatoren
[
  "+" "-" "*" "/" "//" "%" "**"
  "==" "!=" "<" ">" "<=" ">="
  "+=" "-=" "*=" "/=" "%=" "**=" "//="
  "=" "->"
] @operator

[ "(" ")" "[" "]" "{" "}" ] @punctuation.bracket
[ "," ":" ";" "." ] @punctuation.delimiter

; ------------------------------------------------------- Definitionen & Namen
(funktion_definition name: (bezeichner) @function)
(funktion_ausdruck name: (bezeichner) @function)
(klassen_definition name: (bezeichner) @type)
(klassen_definition eltern: (bezeichner) @type)
(typ_hinweis (bezeichner) @type)
(neu_ausdruck klasse: (klassen_pfad (bezeichner) @type))

(parameter name: (bezeichner) @variable.parameter)
(argument name: (bezeichner) @variable.parameter)

(variable_deklaration name: (bezeichner) @variable)
(konstanten_deklaration name: (bezeichner) @constant)
(namensliste (bezeichner) @variable)

(attribut_zugriff attribut: (bezeichner) @property)
(paar schluessel: (zeichenkette) @string.special.key)

; Aufrufe: freie Funktion vs. Methode
(aufruf funktion: (bezeichner) @function.call)
(aufruf funktion: (attribut_zugriff attribut: (bezeichner) @function.method))

; 'dies' verhält sich wie 'self'
((bezeichner) @variable.builtin
  (#eq? @variable.builtin "dies"))

; ------------------------------------------------- Eingebaute Funktionen
((bezeichner) @function.builtin
  (#any-of? @function.builtin
    "drucke" "eingabe" "laenge" "länge" "typ" "ganzzahl" "kommazahl"
    "zeichenkette" "wahrheitswert" "bereich" "sortiere" "anhaengen" "anhängen"
    "entferne" "umkehren" "verbinde" "max" "min" "abs" "runde" "liste"
    "woerterbuch" "wörterbuch" "menge" "summe" "alle" "einige" "aufzaehlen"
    "zippe" "tiefe_kopie"))

; Module der Standardbibliothek
((bezeichner) @namespace
  (#any-of? @namespace
    "mathe" "zufall" "statistik" "datei" "pfad" "json" "regex" "zeit"
    "kodierung" "system"))

; mathe.pi und mathe.e
((attribut_zugriff
   objekt: (bezeichner) @_modul
   attribut: (bezeichner) @constant.builtin)
  (#eq? @_modul "mathe")
  (#any-of? @constant.builtin "pi" "e"))
