/**
 * Admin Dashboard Scripts
 * Handles charts, KPI updates, and DataTables
 * 
 * Dependencies:
 * - jQuery
 * - Chart.js
 * - DataTables
 * 
 * Usage:
 * <script src="{{ url_for('static', filename='js/dashboard.js') }}"></script>
 */

// ============================================================================
// CHART CONFIGURATION
// ============================================================================

function initializeMonthlyChart() {
  const canvas = document.getElementById('monthlySpendChart');
  if (!canvas) {
    console.warn('Monthly chart canvas not found');
    return;
  }
  
  const ctx = canvas.getContext('2d');
  
  // Get data from page (passed from Flask template)
  const labels = window.monthlyLabels || [];
  const dataValues = window.monthlyValues || [];
    // Plugin that draws grey background bars behind each bar
  const shadowBarsPlugin = {
    id: 'shadowBars',
    beforeDatasetsDraw(chart) {
      const { ctx, data, chartArea: { top, bottom }, scales: { x } } = chart;
      const meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data || meta.data.length === 0) return;

      ctx.save();
      meta.data.forEach((bar) => {
        ctx.fillStyle = 'rgba(220, 220, 220, 0.4)';
        const barWidth = bar.width;
        const x0 = bar.x - barWidth / 2;
        const radius = 8;
        const height = bottom - top;

        // Draw rounded rectangle
        ctx.beginPath();
        ctx.moveTo(x0 + radius, top);
        ctx.lineTo(x0 + barWidth - radius, top);
        ctx.quadraticCurveTo(x0 + barWidth, top, x0 + barWidth, top + radius);
        ctx.lineTo(x0 + barWidth, bottom);
        ctx.lineTo(x0, bottom);
        ctx.lineTo(x0, top + radius);
        ctx.quadraticCurveTo(x0, top, x0 + radius, top);
        ctx.closePath();
        ctx.fill();
      });
      ctx.restore();
    }
  };
   window.monthlyChart = new Chart(ctx, {
    type: 'bar',
    plugins: [shadowBarsPlugin],
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Amount Spent ()',
          data: dataValues,
          backgroundColor: [
            // Q1 — Teal (Apr, May, Jun)
            'rgba(78, 205, 196, 0.85)', 'rgba(78, 205, 196, 0.85)', 'rgba(78, 205, 196, 0.85)',
            // Q2 — Amber (Jul, Aug, Sep)
            'rgba(247, 183, 49, 0.85)', 'rgba(247, 183, 49, 0.85)', 'rgba(247, 183, 49, 0.85)',
            // Q3 — Coral (Oct, Nov, Dec)
            'rgba(252, 92, 101, 0.85)', 'rgba(252, 92, 101, 0.85)', 'rgba(252, 92, 101, 0.85)',
            // Q4 — Violet (Jan, Feb, Mar)
            'rgba(165, 94, 234, 0.85)', 'rgba(165, 94, 234, 0.85)', 'rgba(165, 94, 234, 0.85)'
          ],
          borderColor: [
            'rgba(78, 205, 196, 1)', 'rgba(78, 205, 196, 1)', 'rgba(78, 205, 196, 1)',
            'rgba(247, 183, 49, 1)', 'rgba(247, 183, 49, 1)', 'rgba(247, 183, 49, 1)',
            'rgba(252, 92, 101, 1)', 'rgba(252, 92, 101, 1)', 'rgba(252, 92, 101, 1)',
            'rgba(165, 94, 234, 1)', 'rgba(165, 94, 234, 1)', 'rgba(165, 94, 234, 1)'
          ],
          borderWidth: 1,
          borderRadius: 8,
          barPercentage: 0.6,
          categoryPercentage: 0.8
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: function(value) {
              return " " + Number(value).toLocaleString('en-IN');
            }
          }
        }
      }
    }
  });
  
  console.log(' Monthly chart initialized');
}

// ============================================================================
// DATATABLES INITIALIZATION
// ============================================================================

function initializeInvoiceTable() {
  const table = $('#invoiceTable');
  
  if (!table.length) {
    console.warn('Invoice table not found');
    return;
  }
  
  table.DataTable({
    processing: true,
    serverSide: true,
    deferRender: true,
    pageLength: 10,
    
    ajax: {
      url: "/api/invoices",
      type: "POST",
      headers: {
        "X-CSRFToken": $('input[name="csrf_token"]').val()
      },
      data: function(d) {
        // Add filter values to request
        d.vendor = $('input[name="vendor"]').val();
        d.invoice_start_date = $('input[name="invoice_start_date"]').val();
        d.invoice_end_date = $('input[name="invoice_end_date"]').val();
        d.invoice_number = $('input[name="invoice_number"]').val();
        d.created_by = $('input[name="created_by"]').val();
      },
      dataSrc: "data"
    },
    
    columns: [
      { 
        data: "invoice_date",
        render: function(data) {
          if (!data) return "";
          return new Date(data).toLocaleDateString('en-GB', {
            day: '2-digit',
            month: 'short',
            year: 'numeric'
          });
        }
      },
      { 
        data: "date_received",
        render: function(data) {
          if (!data) return "";
          return new Date(data).toLocaleDateString('en-GB', {
            day: '2-digit',
            month: 'short',
            year: 'numeric'
          });
        }
      },
      { data: "vendor" },
      { data: "isd" },
      { data: "invoice_number" },
      { data: "po_number" },
      { data: "msme" },
      { data: "invoice_amount" },
      { data: "gst" },
      { data: "total_amount" },
      { data: "date_submission" },
      { data: "approved_by" },
      { data: "hod_values" },
      { data: "ceo_values" },
      { data: "reviewed_by" },
      { data: "created_by" },
      { data: "tag1" },
      { data: "tag2" },
      { data: "invoice_cleared" },
      { data: "invoice_cleared_date" }
    ]
  });
  
  console.log(' DataTable initialized');
}

// ============================================================================
// FILTER HANDLERS
// ============================================================================

function setupFilterButtons() {
  // Filter button
  $("#filterBtn").on("click", function() {
    $('#invoiceTable').DataTable().ajax.reload();
  });
  
  // Clear button
  $("#clearBtn").on("click", function() {
    $("input[name='vendor']").val("");
    $("input[name='invoice_start_date']").val("");
    $("input[name='invoice_end_date']").val("");
    $("input[name='invoice_number']").val("");
    $("input[name='created_by']").val("");
    
    $('#invoiceTable').DataTable().ajax.reload();
  });
  
  console.log(' Filter buttons configured');
}

// ============================================================================
// API ENDPOINTS
// ============================================================================

async function fetchMonthSpend(month, year) {
  try {
    const response = await fetch(`/api/month_spend?month=${month}&year=${year}`);
    const data = await response.json();
    return data.amount || 0;
  } catch (error) {
    console.error('Error fetching month spend:', error);
    return 0;
  }
}

async function fetchTopCriteria(tag, fromMonth, toMonth) {
  try {
    const response = await fetch(
      `/api/top_criteria?tag=${tag}&from_month=${fromMonth}&to_month=${toMonth}`
    );
    const data = await response.json();
    return data.amount || 0;
  } catch (error) {
    console.error('Error fetching top criteria:', error);
    return 0;
  }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

$(document).ready(function() {
  console.log(' Dashboard scripts loading...');
  
  // Initialize chart
  initializeMonthlyChart();
  
  // // Initialize DataTable
  // initializeInvoiceTable();
  
  // // Setup filter handlers
  // setupFilterButtons();
  
  console.log(' Dashboard initialized');
});