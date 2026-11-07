# OK El til Home Assistant

Få overblik over dit elforbrug og dine elpriser fra **Min OK** direkte i Home Assistant. Integrationen finder automatisk din elaftale og opretter sensorer til både forbrug og omkostninger.

**Version 0.1.2 · 34 sensorer · Danmark · Automatisk opdatering hver 6. time**

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

**Forbrug – Torsdag d. 05/11-26** · **Pris – Torsdag d. 05/11-26**

Hver dag vises med sit faktiske kalenderdatum, også når der endnu ikke er aflæste tal. Når datoen skifter, følger sensorernes navne med, mens deres Home Assistant-identiteter forbliver de samme. Du kan trykke på en dagsensor og finde dato og ugedag i dens attributter.

Sensorerne **Forbrug de seneste 7 afsluttede dage** og **Pris de seneste 7 afsluttede dage** opsummerer kun de aflæsninger, OK har leveret. Attributterne viser både antal dage med målinger og en dateret oversigt over de syv dage. Et manglende døgn tælles **aldrig** som 0 kWh; totalen kan derfor være ufuldstændig.

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

**0.1.2 – Dagsforbrug med danske datoer**

Tilføjer 16 sensorer: individuel kWh og pris for hver af de seneste syv afsluttede kalenderdage samt kWh og pris for den samlede syvdagesperiode. Dagsensorerne viser ugedag og dato og skelner mellem manglende aflæsninger og faktisk nulforbrug.

**0.1.1 – Aflæste dage denne måned**

Tilføjer sensoren **Aflæste dage denne måned**, som tæller antallet af dage med en faktisk kWh-aflæsning. De eksisterende 17 sensorer og deres identiteter er bevaret.

Installation, login og opdatering fra 0.1.0 til 0.1.1 er afprøvet i en kørende Home Assistant-installation.

Se [versionshistorikken](https://github.com/Kasperfcb/ok-el-marketplace/releases) for udgivelser, eller [opret en fejlrapport](https://github.com/Kasperfcb/ok-el-marketplace/issues), hvis noget ikke fungerer.

---

*Denne integration anvender Min OK's uofficielle web-API. Ændringer hos OK kan påvirke funktionaliteten.*
