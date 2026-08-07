const alphaVantageKeys = ["0PPEOPAANBSQ1SL0", "8DH7E8WKEFNTHXS6", "8LXTID5AMXUW4BQ0", "8TALVHO0N2IYNA3R", "IX8AM5YHD38UKYCC", "49YOQY67UX9P1DWJ"];
let alphaVantageIndex = 0;

// ["0PPEOPAANBSQ1SL0", "8DH7E8WKEFNTHXS6", "8LXTID5AMXUW4BQ0", "8TALVHO0N2IYNA3R", "IX8AM5YHD38UKYCC", "49YOQY67UX9P1DWJ"]
function getAlphaVantageKey() {
    alphaVantageIndex += 1;
    alphaVantageIndex = alphaVantageIndex % alphaVantageKeys.length
    return alphaVantageKeys[alphaVantageIndex]
}