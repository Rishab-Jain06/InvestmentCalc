// A file to handle all the requests to the server. Use native fetch to make requests to the server.
// The callback function is called when the request is successful. The callback function takes the response as a parameter.
function request(path, method, callback, body = null) {
    fetch(path, {
        method: method,
        body: body
    }).then((response) => {
        if (response.status == 200) {
            response.text().then((text) => {
                callback(text);
            });
        } else {
            console.log(response.status);
        }
    });
}

// request('http://127.0.0.1:5000/favorite_stocks', 'GET', callback = (response) => {
//     console.log(response);
//     const favoriteStocks = JSON.parse(response);
//     console.log(favoriteStocks);
// });