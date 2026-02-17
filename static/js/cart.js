document.addEventListener("DOMContentLoaded", () => {
  const qtyInputs = document.querySelectorAll(".cart-qty");

  qtyInputs.forEach((input) => {
    input.addEventListener("change", () => {
      if (input.value < 1) input.value = 1;
    });
  });

  const removeButtons = document.querySelectorAll(".remove-item");

  removeButtons.forEach((btn) => {
    btn.addEventListener("click", (e) => {
      if (!confirm("Remove this item from cart?")) {
        e.preventDefault();
      }
    });
  });
});

function addToCart(productId) {
  fetch(`/cart/add-ajax/${productId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    }
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showToast("Added to cart ✅");
    }
  })
  .catch(() => {
    alert("Error adding to cart");
  });
}

/* Simple toast */
function showToast(message) {
  const toast = document.createElement("div");
  toast.innerText = message;
  toast.className =
    "fixed bottom-5 right-5 bg-green-500 text-white px-4 py-2 rounded shadow";
  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 2000);
}

function changeQty(change) {
  const qtyInput = document.getElementById("qty");
  let value = parseInt(qtyInput.value);
  value = isNaN(value) ? 1 : value + change;
  if (value < 1) value = 1;
  qtyInput.value = value;
}

function addToCartWithQty(productId) {
  const qty = document.getElementById("qty").value;

  fetch(`/cart/add-ajax/${productId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qty: qty })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showToast("Added to cart ✅");
    }
  });
}

function syncQty() {
  document.getElementById("buyQty").value =
    document.getElementById("qty").value;
}
