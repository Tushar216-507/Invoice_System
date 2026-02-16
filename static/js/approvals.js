let currentRequestId = null;

function viewDetails(requestId) {
    fetch(`/vendor/request-details/${requestId}`)
        .then(response => response.json())
        .then(data => {
            const content = `
                <table class="table table-bordered">
                    <tr><th>Vendor Name</th><td>${data.vendor_name}</td></tr>
                    <tr><th>Description</th><td>${data.description || 'N/A'}</td></tr>
                    <tr><th>Department</th><td>${data.department || 'N/A'}</td></tr>
                    <tr><th>Address</th><td>${data.vendor_address || 'N/A'}</td></tr>
                    <tr><th>PAN</th><td>${data.PAN || 'N/A'}</td></tr>
                    <tr><th>GSTIN</th><td>${data.GSTIN || 'N/A'}</td></tr>
                    <tr><th>POC Name</th><td>${data.POC || 'N/A'}</td></tr>
                    <tr><th>POC Number</th><td>${data.POC_number || 'N/A'}</td></tr>
                    <tr><th>POC Email</th><td>${data.POC_email || 'N/A'}</td></tr>
                    <tr><th>Requested By</th><td>${data.requested_by_name} (${data.requested_by_email})</td></tr>
                    <tr><th>Request Date</th><td>${new Date(data.request_date).toLocaleString()}</td></tr>
                </table>
            `;
            document.getElementById('modalContent').innerHTML = content;
            new bootstrap.Modal(document.getElementById('detailsModal')).show();
        });
}

function approveVendor(requestId, vendorName) {
    if (!confirm(`Approve vendor: ${vendorName}?`)) return;
    
    fetch(`/vendor/approve/${requestId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert('Error: ' + result.message);
        }
    });
}

function rejectVendor(requestId, vendorName) {
    currentRequestId = requestId;
    document.getElementById('rejectVendorName').textContent = vendorName;
    new bootstrap.Modal(document.getElementById('rejectModal')).show();
}

function confirmReject() {
    const reason = document.getElementById('rejectionReason').value.trim();
    
    if (!reason) {
        alert('Please provide a reason for rejection');
        return;
    }
    
    fetch(`/vendor/reject/${currentRequestId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ reason: reason })
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert('Error: ' + result.message);
        }
    });
}

// Update badge count
function updateApprovalBadge() {
    fetch('/api/pending-count')
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('approval-badge');
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        });
}

// Update every 30 seconds
setInterval(updateApprovalBadge, 30000);
updateApprovalBadge();