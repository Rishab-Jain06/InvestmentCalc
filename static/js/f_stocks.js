async function getFavoriteStocks(ticker) {
    const response = await fetch('/favorite_stocks').then((response) => {
        if (response.status !== 200) {
            onFail(ticker);
        }
        return response;
    });
    const data = await response.json();
    return data;
}

async function addFavoriteStock(ticker) {
    await fetch('/favorite_stocks', {
        method: 'POST',
        headers: {
            'ticker': ticker,
            'action': 'add'
        }
    });
}

async function removeFavoriteStock(ticker) {
    await fetch('/favorite_stocks', {
        method: 'POST',
        headers: {
            'ticker': ticker,
            'action': 'remove'
        }
    });
}