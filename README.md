# OK El (uofficiel) til Home Assistant

Uofficiel Home Assistant-integration til at vise elforbrug
og priser fra [Min OK](https://www.ok.dk/min-ok-forside).
Denne integration er ikke udgivet eller understøttet af OK.

**Testversion 0.1.1:** API-kald er testet mod Min OK, men hele Home Assistant-integrationen er endnu ikke valideret i en kørende Home Assistant-installation. Installér kun, hvis du accepterer at teste en community-integration.

<!-- ha-marketplace:exclude-start -->
[![Åbn OK El i Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=Kasperfcb&repository=ok-el-marketplace&category=integration)

## Installation

Du skal bruge **Home Assistant 2026.11 eller nyere**. Klik på knappen ovenfor for at åbne denne integration direkte i din egen Marketplace, eller tilføj GitHub-linket manuelt:



1. I Home Assistant 2026.11 eller nyere: **Indstillinger → Marketplace → Add from link**.
2. Indsæt repository-URL'en og vælg kategorien **Integration**.
3. Installer **OK El (uofficiel)**.
4. Gå til **Indstillinger → Enheder og tjenester → Tilføj integration → OK El**.
5. Log ind med din egen OK-mail og adgangskode. Aftalenummer findes automatisk.

<!-- ha-marketplace:exclude-end -->

Data opdateres cirka hver 6. time og kan være forsinkede i OK's system.
18 sensorer viser aflæste kWh- og pristal. Manglende data vises som ukendt.
Historiske periodetal er **ikke** en kumulativ energimåler til
Home Assistants Energi-dashboard.

**Sikkerhed:** Adgangskoden gemmes lokalt i Home Assistants config-entry-lager,
ikke på GitHub; cookies holdes midlertidigt i hukommelsen.
Koden bruger et uofficielt OK-web-API, som kan ændre sig.


## Seneste opdatering (0.1.1)

Ny sensor: **Aflæste dage denne måned**. Den tæller kun faktiske kWh-aflæsninger, ikke dage hvor OK endnu ikke har data. De 17 eksisterende sensorer bevares med samme identiteter. Efter opdatering skal Home Assistant genstartes for at indlæse den nye sensor.
