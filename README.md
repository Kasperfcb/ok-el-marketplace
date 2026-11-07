# OK El til Home Assistant

Få overblik over dit elforbrug og dine elpriser fra **Min OK** direkte i Home Assistant. Integrationen finder automatisk din elaftale og opretter sensorer til både forbrug og omkostninger.

**Version 0.2.3 · 34 sensorer · Danmark · Automatisk opdatering hver 6. time**

> **Uofficiel integration:** Projektet er udviklet uafhængigt af OK og er ikke tilknyttet eller understøttet af OK.

<!-- ha-marketplace:exclude-start -->
[![Tilføj OK El til Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Kasperfcb&repository=ok-el-marketplace&category=integration)

## Installation

**Krav:** Home Assistant 2026.11 eller nyere.

**Via Marketplace**

1. Klik på knappen **Åbn i Home Assistant Marketplace** ovenfor.
2. Tilføj repositoryet, og installér **OK El**.
3. Genstart Home Assistant, hvis Marketplace beder om det.
4. Åbn **Indstillinger → Enheder og tjenester → Tilføj integration**.
5. Søg efter **OK El**, og log ind med dine Min OK-oplysninger.

Du behøver ikke kende dit aftalenummer. Det bliver fundet automatisk, når du logger ind.

**Manuel tilføjelse til Marketplace:** Vælg **Add from link**, og brug repositoryadressen:

`https://github.com/Kasperfcb/ok-el-marketplace`

<!-- ha-marketplace:exclude-end -->

## Funktioner

- **Automatisk opsætning:** Log ind med din Min OK-konto. Aftalenummeret bliver fundet automatisk.
- **Elforbrug:** Se registrerede målinger for timer, dage, måneder, kvartaler og år.
- **Priser:** Se omkostninger i kroner og priser pr. kWh, inklusive moms.
- **34 sensorer:** Klar til Home Assistant-dashboards og automatiseringer.
- **Løbende opdatering:** Data hentes cirka hver sjette time.
- **Opdateringer via Marketplace:** Nye versioner kan installeres uden at konfigurere kontoen igen.

## Sensorer

| Område | Tilgængelige oplysninger |
| --- | --- |
| **Timer** | Seneste aflæste time: forbrug og pris pr. kWh |
| **Dage** | Dagens forbrug og pris; seneste aflæste dags forbrug, pris og gennemsnitspris |
| **Seneste 7 dage** | Separate kWh- og prissensorer for hver af de 7 senest afsluttede kalenderdage, plus 7-dages total for begge |
| **Måneder** | Denne og sidste måneds forbrug og pris; antal aflæste dage i indeværende måned |
| **Kvartaler** | Dette kvartals forbrug og pris |
| **År** | Dette og sidste års forbrug og pris |

### Se forbruget på bestemte dage

De historiske dagsensorer viser **ugedag og dato direkte i navnet**, fx:

**Forbrug – 01 – Torsdag d. 05/11-26** · **Pris – 01 – Torsdag d. 05/11-26**

Hver dag vises med sit faktiske kalenderdatum, også når der endnu ikke er aflæste tal. Når datoen skifter, følger sensorernes navne med, mens deres Home Assistant-identiteter forbliver de samme. Du kan trykke på en dagsensor og finde dato og ugedag i dens attributter.

Sensorerne **Forbrug de seneste 7 afsluttede dage** og **Pris de seneste 7 afsluttede dage** opsummerer kun de aflæsninger, OK har leveret. Attributterne viser både antal dage med målinger og en dateret oversigt over de syv dage. Et manglende døgn tælles **aldrig** som 0 kWh; totalen kan derfor være ufuldstændig.

## Historik-dashboard i Home Assistant

Fra version 0.2.0 følger et dashboardkort med integrationen. Kortet viser **interaktive grafer, datotabeller og summer** for time-, dags-, måneds-, kvartals- og årsdata samt elpriser inkl. moms.

**Sådan tilføjer du kortet**

1. Installér opdateringen via Marketplace og genstart Home Assistant.
2. Åbn dit Home Assistant-dashboard, vælg **Rediger dashboard → Tilføj kort → Manuel**.
3. Indsæt:

```yaml
type: custom:ok-el-history-card
```

4. Gem kortet. Det viser straks de historiske målinger, integrationen allerede har hentet.
5. Tryk på **Hent historik** i kortet for at indlæse ældre data. Du kan vælge 6, 12, 24 eller 36 måneders dagsdata samt timeforbrug for 7, 14, 30, 90, 180, 365 dage eller alle aflæste dage. En import kan tage tid, og data bliver hentet i baggrunden.

**Hvis korttypen ikke vises:** Opdatér til **0.2.1**, genstart Home Assistant, og genindlæs browseren med **Cmd+Shift+R / Ctrl+Shift+R**. Denne version retter automatisk registrering af kortet i Home Assistants Lovelace-ressourcer.

Hvis din installation bruger YAML-styrede dashboardressourcer, eller hvis automatisk registrering stadig ikke virker, kan du tilføje `/ok-el-assets/ok-el-history-card.js?v=0.2.1` under **Indstillinger → Dashboards → ⋮ → Ressourcer** som **JavaScript-modul**. Opret kun ressourcen manuelt, hvis den ikke allerede findes.

**Nyt i 0.2.2:** Hold musen over en søjle, eller tryk på den på mobil, for at se **dato, kWh, kroner inkl. moms og kr./kWh** samlet. Den lokale historikimport viser nu fremdrift under hentningen og genbruger allerede gemte ældre måneder og fuldførte timedage. De to nyeste måneder kontrolleres stadig for forsinkede målinger og rettelser.

**Nyt i 0.2.3:** Valget **Timedata → Alle aflæste dage** fjerner den gamle 30-dagesgrænse. Du kan også vælge 90, 180 eller 365 dage. Importen arbejder i mindre portioner på højst 21 dage, gemmer efter hver portion og kan fortsætte efter en afbrydelse. Timer vises i overskuelige vinduer på cirka 30 dage, som du kan bladre frem og tilbage i. Knappen **Opdater visning** bliver straks blå med teksten *Opdaterer…*, og viser *Opdateret*, når kortet er genindlæst. Den knap genindlæser eksisterende lokal historik; det er fortsat **Hent historik**, der kontakter OK.

**Privat og vedvarende:** Historiske data gemmes i Home Assistants lokale, private `.storage`-lager, ikke som tusindvis af sensorattributter. De forbliver tilgængelige efter genstart og bliver opdateret, når integrationen henter nye aflæsninger. Kun Home Assistant-administratorer kan tilgå den fulde historik via kortets godkendte API.

**Omfang:** Historikimporten understøtter aktuelt op til 36 måneders dagsdata og timedata for alle tilgængelige aflæste dage inden for den valgte periode, plus månedlige, kvartalsvise og årlige sammenligninger for perioden. Den indeholder **ikke fakturaer**. Antallet af faktisk tilgængelige målinger afhænger af OK.

### Sådan skal tallene forstås

OK's målerdata kan være forsinkede. Hvis en aflæsning ikke er tilgængelig, viser integrationen **Ukendt** i stedet for at registrere et fejlagtigt forbrug på 0 kWh.

Priserne er baseret på oplysningerne fra Min OK og kan afvige fra de endelige beløb på din faktura.

**Home Assistants Energi-dashboard:** De nuværende sensorer viser registrerede periodeværdier. De er ikke en kumulativ elmåler og er derfor endnu ikke beregnet til direkte brug som energikilde i Energi-dashboardet.

## Privatliv og sikkerhed

- Loginoplysninger opbevares i Home Assistants lokale konfigurationslager.
- Sessionscookies bruges under datahentningen og opbevares kun midlertidigt i hukommelsen.
- Dine loginoplysninger og forbrugsdata bliver ikke gemt i projektets GitHub-repository.
- Integrationen kommunikerer med OK via HTTPS og kræver ingen åbne indgående porte.

## Seneste ændringer

**0.2.3 – Fuld timehistorik og tydelig opdateringsknap**

Timedata kan nu hentes for 90, 180, 365 dage eller alle tilgængelige aflæste dage inden for de valgte måneder (højst 36). Importen gemmer undervejs i 21-dagesportioner og fortsætter efter Home Assistant-genstart. Timegrafen kan bladres gennem ældre perioder uden at indlæse tusindvis af søjler på én gang. *Opdater visning* bliver blå ved klik og viser tydeligt, når visningen er opdateret.


**0.2.2 – Hurtigere historik og detaljer ved søjler**

Grafens søjler har en tydelig tooltip, som viser både kWh, samlet pris, gennemsnitspris og dato. Historikimporten viser løbende fremdrift og springer tidligere hentede ældre måneder og komplette timedage over. Dine eksisterende sensorer, personlige data og login ændres ikke.


**0.2.1 – Automatisk indlæsning af historikkort**

Retter en fejl i registreringen af dashboardkortet på Home Assistant 2026.11+. Kortet tilføjes nu automatisk som en Lovelace-ressource i standardopsætningen. Eksisterende sensorer og loginopsætningen påvirkes ikke. Genstart Home Assistant og genindlæs dashboardet efter opdatering.


**0.2.0 – Historik-dashboard og datofølge**

Tilføjer et indbygget historikkort med grafer og tabeller, privat lokal lagring og mulighed for at hente ældre målinger. Dagsensorerne får nummerering 01–07, så nyeste dato sorteres først. De 34 eksisterende sensorer og deres unikke ID'er bevares. Kortet er endnu ikke live-testet på en brugers Home Assistant-installation.

**0.1.2 – Dagsforbrug med danske datoer**

Tilføjer 16 sensorer: individuel kWh og pris for hver af de seneste syv afsluttede kalenderdage samt kWh og pris for den samlede syvdagesperiode. Dagsensorerne viser ugedag og dato og skelner mellem manglende aflæsninger og faktisk nulforbrug.

**0.1.1 – Aflæste dage denne måned**

Tilføjer sensoren **Aflæste dage denne måned**, som tæller antallet af dage med en faktisk kWh-aflæsning. De eksisterende 17 sensorer og deres identiteter er bevaret.

Installation, login og opdatering fra 0.1.0 til 0.1.1 er afprøvet i en kørende Home Assistant-installation.

Se [versionshistorikken](https://github.com/Kasperfcb/ok-el-marketplace/releases) for udgivelser, eller [opret en fejlrapport](https://github.com/Kasperfcb/ok-el-marketplace/issues), hvis noget ikke fungerer.

---

*Denne integration anvender Min OK's uofficielle web-API. Ændringer hos OK kan påvirke funktionaliteten.*
