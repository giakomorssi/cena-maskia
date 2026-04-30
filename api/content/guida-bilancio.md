# Guida alla compilazione del Bilancio

## Perche' esiste il bilancio
Il bilancio e' lo strumento con cui ogni squadra rende conto della propria gestione economica e mantiene il **fair play finanziario** della lega. Garantisce competitivita' equilibrata e impedisce che le squadre accumulino perdite ripetute senza conseguenze.

## Scadenza
Il bilancio deve essere caricato entro il **15 luglio** della stagione di riferimento.

## Obbligatorieta' e conseguenze
- La compilazione e' **obbligatoria** per tutte le squadre della lega.
- La mancata presentazione comporta **penalita' in classifica** e divieto di operazioni di mercato fino alla regolarizzazione.

---

## Step 1 - Valore della produzione (Ricavi)
Inserisci nella scheda `ricavi` del template Excel tutte le voci attive:

| Voce | Descrizione |
| --- | --- |
| Capitale sociale | Apporto iniziale della proprieta' |
| Cessioni calciatori | Solo la parte di ricavo netto, non plusvalenza |
| Sponsor | Eventuali sponsorizzazioni di lega |
| Premi | Premi piazzamento (campionato, coppa, ecc.) |
| Ricavi stadio | Botteghino, abbonamenti, hospitality |

## Step 2 - Costi della produzione
Nella scheda `costi`:

| Voce | Descrizione |
| --- | --- |
| Acquisto giocatori | Spesa cash per cartellini |
| Stipendi | Monte ingaggi annuale |
| Costi stadio | Manutenzione, gestione |
| Multe | Sanzioni disciplinari |
| Costi vari | Tasse iscrizione, costi accessori |

## Step 3 - Ammortamenti
Gli ammortamenti vanno **separati** nella scheda `ammortamenti` perche' dipendono dalla **fascia di costo** del giocatore.

| Fascia di costo | Aliquota |
| --- | --- |
| 1 - 9 | 100% |
| 10 - 19 | 95% |
| 20 - 34 | 90% |
| 35 - 49 | 85% |
| 50 - 69 | 75% |
| 70 - 89 | 65% |
| 90 - 120 | 60% |
| 120+ | 60% |

**Esempio**: giocatore acquistato a **40 crediti** -> fascia 35-49 -> ammortamento = `40 * 85% = 34`.

Nel template, una riga per giocatore con `costo` e `fascia` (`1-9`, `10-19`, `20-34`, `35-49`, `50-69`, `70-89`, `90-120`, `120+`).

## Step 4 - Plusvalenze e minusvalenze
Nella scheda `plus_minus`:
- `valore_cessione` = quanto incassi dalla cessione
- `valore_libro` = valore residuo a bilancio del giocatore (costo - ammortamenti gia' applicati)
- **Plusvalenza** se positiva, **minusvalenza** se negativa.

Il delta entra direttamente nel calcolo del risultato.

**Esempio**: cedi un giocatore con valore di libro `15` a `25` -> plusvalenza di `10`.

## Step 5 - Chiusura del bilancio
Il sistema calcola:

`Utile = Ricavi + (Plus/Minusvalenze) - Costi - Ammortamenti`

- **Utile positivo** -> nessuna sanzione.
- **Utile negativo (perdita)** -> sanzione automatica in base alle soglie:

| Livello | Perdita fino a | Penalita' |
| --- | --- | --- |
| Lieve | soglia leggera | -1 punto |
| Media | soglia media | -3 punti + riduzione rosa |
| Grave | soglia pesante | -6 punti + riduzione rosa estesa |
| Gravissima | oltre soglia pesante | -10 punti + blocco mercato |

I valori esatti delle soglie sono configurabili e pubblicati a inizio stagione.

---

## Come caricare il bilancio
1. Scarica il **template Excel** dalla pagina Bilanci.
2. Compila le 4 schede: `ricavi`, `costi`, `ammortamenti`, `plus_minus`.
3. Inviane copia all'amministratore della lega che effettuera' l'upload.
4. Controlla in pagina **Bilanci** il risultato calcolato e l'eventuale sanzione.
