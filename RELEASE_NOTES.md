## Nyt i OK El 0.2.3

### Flere timedata fra Min OK

- **Timedata** har nu valgene **7, 14, 30, 90, 180, 365 dage** og **Alle aflæste dage**. Du kan kombinere med 6–36 måneders dagsdata.
- **Alle** betyder alle aflæste dage inden for de valgte måneder og de tidsdata, som OK faktisk kan levere. Det er ikke en garanti for, at OK har hele perioden.
- Importen køres forsigtigt i portioner på højst **21 timedage**, hvor aflæsninger og fremdrift gemmes i Home Assistants private lager efter hver portion.
- Hvis Home Assistant genstarter midt i et tidligere bestilt importjob, fortsætter importen automatisk ud fra den gemte historik.
- Timehistorikken kan gennemses i vinduer på cirka 30 dage med **Ældre timer / Nyere timer**. Historiske målinger forsvinder ikke, når du skifter vindue.

### Mere tydelig opdateringsknap

- **Opdater visning** bliver straks blå og viser **↻ Opdaterer…**, så du kan se, at trykket er registreret.
- Når lokal datahentning er afsluttet, vises **✓ Opdateret**. Fejl vises tydeligt.
- Knappen genindlæser historikken fra Home Assistant; den laver ikke et separat login hos OK. Til nye historiske målinger bruges **Hent historik**.

Alle 34 eksisterende sensorer og loginindstillinger bevares. Kompatibilitet og brugerflade er testet automatisk; langvarig import af alle tilgængelige timedage skal valideres i en kørende Home Assistant.

**Efter opdatering:** Genstart Home Assistant og genindlæs dashboardet med Ctrl+Shift+R (Windows) eller Cmd+Shift+R (Mac).
