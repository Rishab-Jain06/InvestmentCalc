// APPLIED TO ALL PAGES
function scrollToTop() {
  window.scrollTo(0, 0);
}

window.addEventListener('load', scrollToTop);

// Function to show spinner and hide data
function loading() {
    const data = document.getElementById("data")
    if(data !== null){
      data.style.display = 'none';
    }
    const spinner = document.getElementById("loadSpinner");
    if (spinner !== null) {
      spinner.parentElement.style.display = 'block';
      spinner.style.display = 'block';
    }
}

// Example starter JavaScript for disabling form submissions if there are invalid fields.
(() => {
    'use strict'
  
    // Fetch all the forms we want to apply custom Bootstrap validation styles to
    const forms = document.querySelectorAll('.form-control')
  
    // Loop over them and prevent submission
    Array.from(forms).forEach(form => {
      form.addEventListener('submit', event => {
        if (!form.checkValidity()) {
          event.preventDefault()
          event.stopPropagation()
        } else {
          loading();
        }
  
        form.classList.add('was-validated')
      }, false)
    })
  })()

// index-search-input - autocomplete-results-index
// nav-search-input-dropdown - autocomplete-results-nav-dropdown
// nav-search-input - autocomplete-results-nav
// ticker - autocomplete-results

// document.addEventListener('keyup', async (event) => {
//     const inputs = [document.getElementById('ticker'), document.getElementById('nav-search-input-dropdown'), document.getElementById('index-search-input')]
//     const results = [document.getElementById('autocomplete-results'), document.getElementById('autocomplete-results-nav-dropdown'), document.getElementById('autocomplete-results-index')]
    
//     const input = inputs.find((input) => input !== null && input !== undefined && input === document.activeElement)
//     const result = results[inputs.indexOf(input)]
    

//     if(input != document.activeElement) return;


//     var name = event.key;
//     // console.log(input.value);
//     // console.log(api_keys[index])

//     if (!input.value) {
//       if (result != null) {
//         if(!result.classList.contains('hidden')) result.classList.add('hidden')
//       }
//     }

//     let keyword = input.value;

//     if(result != null) result.classList.remove('hidden')
//     else return
//     // console.log(result)
//     const data = await fetch(`https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords=${keyword}&apikey=${getAlphaVantageKey()}`).then((response) => {
//         if (response.status !== 200) {
//             onFail(ticker);
//         }
//         return response.json();
//     });

//     // console.log(data)
//     let count = 0
//     let returnHTML = ''
//     let bestMatches = data['bestMatches']
//     if (bestMatches) {
//       bestMatches.forEach((match) => {
//           count++;
//           if(count > 5) return
//           returnHTML += `
//               <div class="join-item px-6 py-3 hover:bg-"><a class="hover:underline" href="/search?ticker=${match["1. symbol"]}"><span>${match["1. symbol"]}</span> - <span>${match["2. name"]}</span></a></div>
//           `
//       })
//     }


//     if(result != null)  result.innerHTML = returnHTML

// }, {
//   passive: true
// });

  