// Submit Event Listener for Search Form on Navbar
let navSearchForm = document.getElementById("nav-search-form");
navSearchForm.addEventListener("submit", function(event) {
    event.preventDefault();
    let ticker = document.getElementById("nav-search-input").value;
    document.getElementById("nav-search-input").value = "";
    console.log(ticker);

    // Redirect to the search page and fill out the form.
    window.location.href = "/search?ticker=" + ticker;
});

let navSearchFormDropdown = document.getElementById("nav-search-form-dropdown");
navSearchFormDropdown.addEventListener("submit", function(event) {
    event.preventDefault();
    let ticker = document.getElementById("nav-search-input-dropdown").value;
    document.getElementById("nav-search-input-dropdown").value = "";
    console.log(ticker);

    // Redirect to the search page and fill out the form.
    window.location.href = "/search?ticker=" + ticker;
});