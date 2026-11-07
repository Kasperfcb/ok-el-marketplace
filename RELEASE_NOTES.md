## Nyheder i 0.2.2 – Overskuelig graf og hurtigere historik

- Hold musen over en graf-søjle for at se **ugedag/dato, kWh, pris inkl. moms og pris pr. kWh** i samme tooltip. Du kan også trykke på søjlen på telefon og bruge tastaturet.
- Historikimporten viser nu fremdrift: antal behandlede trin og den periode, der arbejdes med.
- Tidligere indlæste **ældre måneder og fuldførte time-døgn** genbruges automatisk ved næste import i stedet for at blive hentet igen.
- De to seneste måneder genindlæses fortsat, så efterregistrerede målinger hos OK og prisrettelser kan fanges.
- Historiske måneder, der er undersøgt, men hvor OK ikke har aflæsninger, bliver registreret lokalt, så gentagne importer normalt kan springe dem over.
- Forbruget gemmes stadig privat i Home Assistant, og de eksisterende **34 sensorer** samt deres ID'er bevares.

**Efter opdatering:** Installér via Marketplace, genstart Home Assistant og genindlæs dashboardet med Ctrl+Shift+R / Cmd+Shift+R. Prøv derefter at holde musen over en søjle og hente historik igen.

**Bemærk:** Den faktiske hastighed afhænger af OK's server. Integrationen laver fortsat API-kald sekventielt for at undgå at overbelaste OK. Frontend og den optimerede historikimport er testet med automatiske kode- og enhedstests, men endnu ikke på brugerens live Home Assistant.
