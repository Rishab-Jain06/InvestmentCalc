async function calculateTax(e) {
    e.preventDefault();
    var sellingPrice = document.getElementById("selling_price").value;
    var costBasis = document.getElementById("cost_basis").value;
    var holdingPeriod = document.getElementById("holding_period").value;
    var taxableIncome = document.getElementById("taxable_income").value;

    const response = await fetch('/calculate-tax', {
        method: 'POST',
        body: JSON.stringify({
            selling_price: sellingPrice,
            cost_basis: costBasis,
            holding_period: holdingPeriod,
            taxable_income: taxableIncome
        }),
        headers: {
            'Content-Type': 'application/json'
        }
    }).then((response) => {
        if (response.status !== 200) {
            onFail(ticker);
        }
        return response;
    });
    capitalGainsTax = (await response.json())['capital_gains_tax'];
    document.getElementById("capital-gains-tax").innerHTML = `$${capitalGainsTax}`;
    document.getElementById("result").style.display = "block";
}

document.getElementById("calculate-tax").addEventListener("click", calculateTax);