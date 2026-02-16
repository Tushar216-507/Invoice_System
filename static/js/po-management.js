/**
 * Purchase Order Management Scripts
 * Handles PO creation, editing, and deletion
 * 
 * Dependencies:
 * - jQuery
 * - Bootstrap 5
 * 
 * Usage:
 * <script src="{{ url_for('static', filename='js/po-management.js') }}"></script>
 */

// ============================================================================
// VENDOR DATA (passed from Flask template)
// ============================================================================
// Add this helper function at the top of po-management.js
let vendorMap = {};
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function initializeVendorMap(vendorData) {
  vendorData.forEach(vendor => {
    vendorMap[vendor.vendor_name] = {
      address: vendor.vendor_address || '',
      shortform: vendor.shortforms_of_vendors || '',
      pan: vendor.PAN || '',
      gstin: vendor.GSTIN || '',
      poc: vendor.POC || '',
      poc_number: vendor.POC_number || '',
      poc_email: vendor.POC_email || ''
    };
  });
  
  console.log(`✅ Loaded ${Object.keys(vendorMap).length} vendors`);
}

// ============================================================================
// PO NUMBER GENERATION
// ============================================================================

async function generatePONumber(vendorName, poDate) {
  try {
    const csrfToken = document.getElementById("csrf_token")?.value;
    
    if (!csrfToken) {
      throw new Error('CSRF token not found');
    }
    
    const response = await fetch('/po/generate_number', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify({
        vendor_name: vendorName,
        po_date: poDate
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      return data.po_number;
    } else {
      throw new Error(data.message || 'Failed to generate PO number');
    }
    
  } catch (error) {
    console.error('❌ Error generating PO number:', error);
    return null;
  }
}

// ============================================================================
// VENDOR DETAILS & PO NUMBER HANDLING
// ============================================================================

async function fillVendorDetails(vendorName) {
  const vendor = vendorMap[vendorName];
  const isMandatory = document.getElementById("is_po_mandatory")?.checked;
  
  if (!vendor) {
    console.warn('No vendor data found for:', vendorName);
    return;
  }
  
  // Always fill vendor address
  const addressField = document.getElementById('vendor_address');
  if (addressField) {
    addressField.value = vendor.address;
  }
  
  // Only generate PO number if PO is mandatory
  if (!isMandatory) {
    console.log('PO not mandatory, skipping PO number generation');
    return;
  }
  
  const poDate = document.getElementById("po_date")?.value;
  
  if (!poDate) {
    alert("Please select PO Date first");
    return;
  }
  
  // Generate PO Number
  const poNumber = await generatePONumber(vendorName, poDate);
  
  if (poNumber) {
    const poNumberField = document.getElementById('add_po_number');
    if (poNumberField) {
      poNumberField.value = poNumber;
      poNumberField.readOnly = true;
      console.log('✅ PO Number generated:', poNumber);
    }
  } else {
    alert('Could not generate PO number. Please enter manually.');
  }
}

// ============================================================================
// PO FORM MANAGEMENT
// ============================================================================

function togglePOSection() {
  const poCheckbox = document.getElementById("is_po_mandatory");
  const poFields = document.getElementById("poFields");
  const poNumberInput = document.getElementById("add_po_number");
  const poDateInput = document.getElementById("po_date");
  
  if (!poCheckbox || !poFields) return;
  
  if (poCheckbox.checked) {
    // Show PO fields
    poFields.style.display = "flex";
    if (poNumberInput){
      poNumberInput.required = true;
      poNumberInput.closest('.col-md-6').style.display = "block";
    }
    if (poDateInput) poDateInput.required = true;
  } else {
    // Hide PO fields
    poFields.style.display = "flex";
    if (poNumberInput) {
      poNumberInput.value = "";
      poNumberInput.required = false;
      poNumberInput.readOnly = false;
      poNumberInput.closest('.col-md-6').style.display = "none";
    }
    if (poDateInput) {
      poDateInput.required = true;
    }
  }
  
  updateVendorLockState();
}

function updateVendorLockState() {
  const isMandatory = document.getElementById("is_po_mandatory")?.checked;
  const vendorInput = document.getElementById('vendor_name');
  const poDateInput = document.getElementById('po_date');
  
  if (!vendorInput) return;
  
  if (isMandatory) {
    // When PO is mandatory, vendor is disabled until PO date is selected
    vendorInput.disabled = !poDateInput?.value;
  } else {
    // When PO is not mandatory, vendor is always enabled
    vendorInput.disabled = false;
  }
}

// ============================================================================
// ITEM MANAGEMENT
// ============================================================================

function addItemRow() {
  const itemsBody = document.getElementById('itemsBody');
  if (!itemsBody) return;
  
  itemsBody.insertAdjacentHTML("beforeend", `
    <tr>
      <td><input class="form-control" required></td>
      <td><input class="form-control" type="number" step="0.01"></td>
      <td><input class="form-control" type="number" step="0.01"></td>
      <td><input class="form-control" type="number" step="0.01" required></td>
      <td>
        <button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove()">
          ❌
        </button>
      </td>
    </tr>
  `);
}

function addEditItemRow() {
  const itemsBody = document.getElementById('editItemsBody');
  if (!itemsBody) return;
  
  itemsBody.insertAdjacentHTML("beforeend", `
    <tr>
      <td><input class="form-control" required></td>
      <td><input class="form-control" type="number" step="0.01"></td>
      <td><input class="form-control" type="number" step="0.01"></td>
      <td><input class="form-control" type="number" step="0.01" required></td>
      <td>
        <button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove()">
          ❌
        </button>
      </td>
    </tr>
  `);
}

// ============================================================================
// PO CRUD OPERATIONS
// ============================================================================

async function deletePO(id) {
  if (!confirm("Are you sure you want to delete this PO?")) return;
  
  try {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
    
    const response = await fetch(`/po/delete/${id}`, {
      method: "POST",
      headers: {"X-CSRFToken": csrfToken},
      credentials: "include"
    });
    
    const data = await response.json();
    
    if (data.success) {
      alert('PO deleted successfully');
      location.reload();
    } else {
      alert(data.message || 'Failed to delete PO');
    }
    
  } catch (error) {
    console.error('❌ Error deleting PO:', error);
    alert('Failed to delete PO. Please try again.');
  }
}

async function editPO(id) {
  try {
    // Fetch PO details
    const response = await fetch(`/po/detail/${id}`);
    const data = await response.json();
    
    if (data.error) {
      alert(data.error);
      return;
    }
    
    // Populate the edit form
    document.getElementById('edit_po_id').value = data.id;
    document.getElementById('edit_po_number').value = data.po_number || '';
    document.getElementById('edit_po_date').value = data.po_date || '';
    document.getElementById('edit_vendor_name').value = data.vendor_name || '';
    document.getElementById('edit_vendor_address').value = data.vendor_address || '';
    
    // Clear and populate items
    const tbody = document.getElementById('editItemsBody');
    tbody.innerHTML = '';
    
    if (data.items && data.items.length > 0) {
      data.items.forEach(item => {
        tbody.insertAdjacentHTML("beforeend", `
          <tr>
            <td><input class="form-control" value="${item.product_description || ''}" required></td>
            <td><input class="form-control" type="number" step="0.01" value="${item.quantity || ''}"></td>
            <td><input class="form-control" type="number" step="0.01" value="${item.rate || ''}"></td>
            <td><input class="form-control" type="number" step="0.01" value="${item.line_total || ''}" required></td>
            <td>
              <button type="button" class="btn btn-danger btn-sm" onclick="this.closest('tr').remove()">
                ✕
              </button>
            </td>
          </tr>
        `);
      });
    } else {
      // Add at least one empty row
      addEditItemRow();
    }
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('editPOModal'));
    modal.show();
    
  } catch (error) {
    console.error('❌ Error loading PO details:', error);
    alert('Failed to load PO details. Please try again.');
  }
}
function setupEditPOFormSubmission() {
  const editPOForm = document.getElementById("editPOForm");
  
  if (!editPOForm) return;
  
  editPOForm.addEventListener("submit", async function(e) {
    e.preventDefault();
    
    const poId = document.getElementById('edit_po_id').value;
    
    // Collect items
    let items = [];
    document.querySelectorAll("#editItemsBody tr").forEach(row => {
      let inputs = row.querySelectorAll("input");
      items.push({
        description: inputs[0].value,
        qty: parseFloat(inputs[1].value) || null,
        rate: parseFloat(inputs[2].value) || null,
        total: parseFloat(inputs[3].value)
      });
    });
    
    const payload = {
      items: items
    };
    
    try {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
      
      const response = await fetch(`/po/update/${poId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken
        },
        credentials: "include",
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert(data.message);
        location.reload();
      } else {
        alert(data.message || 'Failed to update PO');
      }
      
    } catch (error) {
      console.error('❌ Error updating PO:', error);
      alert('Failed to update PO. Please try again.');
    }
  });
}
// ============================================================================
// FORM SUBMISSION
// ============================================================================

function setupPOFormSubmission() {
  const addPOForm = document.getElementById("addPOForm");
  
  if (!addPOForm) return;
  
  addPOForm.addEventListener("submit", async function(e) {
    e.preventDefault();
    
    // Collect items
    let items = [];
    document.querySelectorAll("#itemsBody tr").forEach(row => {
      let inputs = row.querySelectorAll("input");
      items.push({
        description: inputs[0].value,
        qty: parseFloat(inputs[1].value) || null,
        rate: parseFloat(inputs[2].value) || null,
        total: parseFloat(inputs[3].value)
      });
    });
    
    const isMandatory = document.getElementById("is_po_mandatory")?.checked;
    
    let payload = {
      vendor_name: document.getElementById('vendor_name')?.value,
      vendor_address: document.getElementById('vendor_address')?.value,
      items
    };
    
    if (isMandatory) {
      payload.po_number = document.getElementById("add_po_number")?.value;
      const poDate = document.getElementById('po_date')?.value;
      payload.po_date = poDate ? poDate.split("-").reverse().join("/") : null;
    } else {
      payload.po_number = null;
      const poDate = document.getElementById('po_date')?.value;
      payload.po_date = poDate ? poDate.split("-").reverse().join("/") : null;
    }
    
    try {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content");
      
      const response = await fetch("/po/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken
        },
        credentials: "include",
        body: JSON.stringify(payload)
      });
      
      const data = await response.json();
      
      if (data.success) {
        alert(data.message);
        location.reload();
      } else {
        alert(data.message || 'Failed to create PO');
      }
      
    } catch (error) {
      console.error('❌ Error creating PO:', error);
      alert('Failed to create PO. Please try again.');
    }
  });
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
  console.log('📋 PO management scripts loading...');
  
  // Setup event listeners
  const poCheckbox = document.getElementById("is_po_mandatory");
  const vendorInput = document.getElementById('vendor_name');
  const poDateInput = document.getElementById('po_date');
  const addPOModal = document.getElementById('addPOModal');
  
  if (poCheckbox) {
    poCheckbox.addEventListener("change", function() {
      togglePOSection();
      updateVendorLockState();
    });
  }
  
  if (poDateInput) {
    poDateInput.addEventListener("change", updateVendorLockState);
  }
  
  if (vendorInput) {
    vendorInput.addEventListener('change', function() {
      fillVendorDetails(this.value);
    });
  }
  
  // Initialize on page load
  togglePOSection();
  updateVendorLockState();
  
  // Re-initialize when modal opens
  if (addPOModal) {
    addPOModal.addEventListener('shown.bs.modal', function() {
      togglePOSection();
      updateVendorLockState();
    });
  }
  
  // Setup form submission
  setupPOFormSubmission();
  setupEditPOFormSubmission();
  
  console.log('✅ PO management initialized');
});