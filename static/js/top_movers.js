
async function getStocks() {
    const data = await fetch(`https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey=${getAlphaVantageKey()}`).then((response) => {
        if(response.status !== 200) {
            onFail(ticker);
        }
        return response.json();
    })

    // console.log(data)
    const top_gainers = data['top_gainers']
    const top_losers = data['top_losers']
    const top_movers = data['most_actively_traded']
    const isIndexPage = window.location.pathname === '/'

    let gainer_rows = ``
    top_gainers.forEach((stock, index) => {
        if(isIndexPage && index > 10) return;
        gainer_rows += `
            <tr class="hover text-green-400">
                <td>${index+1}</td>
                <td><a href="/search?ticker=${stock['ticker']}" class="hover:underline">${stock['ticker']}</a></td>
                <td>${stock['change_percentage']}</td>
                <td>${stock['price']}</td>
            </tr>
        `
    })

    let loser_rows = ``
    top_losers.forEach((stock, index) => {
        if(isIndexPage && index > 10) return;
        loser_rows += `
            <tr class="hover text-red-400">
                <td>${index+1}</td>
                <td><a href="/search?ticker=${stock['ticker']}" class="hover:underline">${stock['ticker']}</a></td>
                <td>${stock['change_percentage']}</td>
                <td>$${stock['price']}</td>
            </tr>
        `
    })

    let mover_rows = ``
    top_movers.forEach((stock, index) => {
        if(isIndexPage && index > 10) return;
        let color = stock['change_amount'] > 0 ? 'text-green-400' : 'text-red-400'
        mover_rows += `
            <tr class="hover ${color}">
                <td>${index+1}</td>
                <td><a href="/search?ticker=${stock['ticker']}" class="hover:underline">${stock['ticker']}</a></td>
                <td>${stock['change_percentage']}</td>
                <td>${stock['price']}</td>
            </tr>
        `
    })

    const top_gainers_tables = document.querySelector('.gainers')
    const top_losers_tables = document.querySelector('.losers')
    const top_movers_tables = document.querySelector('.movers')

    top_gainers_tables.innerHTML = `
        <thead>
            <tr class="hover font-medium">
                <th></th>
                <th>Ticker</th>
                <th>% Chg</th>
                <th>Last Price</th>
            </tr>
        </thead>
        <tbody class="text-green-400">
        ${gainer_rows}
        </tbody>
        `
    // console.log(top_gainers_tables.innerHTML)


    top_losers_tables.innerHTML = `
        <thead>
            <tr class="hover font-medium">
                <th></th>
                <th>Ticker</th>
                <th>% Chg</th>
                <th>Last Price</th>
            </tr>
        </thead>
        <tbody class="text-red-400">
            ${loser_rows}
        </tbody>
    `


    top_movers_tables.innerHTML = `
        <thead>
            <tr class="hover font-medium">
                <th></th>
                <th>Ticker</th>
                <th>% Chg</th>
                <th>Last Price</th>
            </tr>
        </thead>
        <tbody class="">
            ${mover_rows}
        </tbody>
    `



    
}

function onFail(ticker) {
    // If stock ticker not found or data not available, then reload the page with flash message.
    console.log("error="+ticker);
}

document.addEventListener('DOMContentLoaded', async() => {
    await getStocks();   
});
