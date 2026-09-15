window.PV = window.PV || {};

PV.gridDefaults = {
  defaultColDef: {
    sortable: true,
    filter: true,
    resizable: true,
    minWidth: 90,
  },
  animateRows: false,
  pagination: true,
  paginationPageSize: 20,
  paginationPageSizeSelector: [10, 20, 50, 100],
  rowHeight: 34,
  headerHeight: 34,
  domLayout: "autoHeight",
  overlayNoRowsTemplate: "<span class='grid-empty'>표시할 데이터가 없습니다.</span>",
};

PV.initGrid = function (elId, columnDefs, rowData, overrides) {
  var el = document.getElementById(elId);
  if (!el) return null;
  var options = Object.assign({}, PV.gridDefaults, {
    columnDefs: columnDefs,
    rowData: rowData,
  }, overrides || {});
  return agGrid.createGrid(el, options);
};

PV.exportGridToExcel = function (gridApi, filename, sheetName) {
  var rows = [];
  var cols = gridApi.getColumnDefs().filter(function (c) { return c.field && !c.hide; });
  gridApi.forEachNodeAfterFilterAndSort(function (node) {
    var row = {};
    cols.forEach(function (c) {
      row[c.headerName || c.field] = node.data ? node.data[c.field] : "";
    });
    rows.push(row);
  });
  var ws = XLSX.utils.json_to_sheet(rows);
  var wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName || "Sheet1");
  XLSX.writeFile(wb, filename || "export.xlsx");
};

PV.chartPalette = {
  critical: "#dc4a4a",
  criticalSoft: "#f4b7b7",
  warning: "#d99a2b",
  warningSoft: "#f0d38f",
  info: "#3d6fd1",
  infoSoft: "#a9c2ed",
  grid: "#e8eaee",
  text: "#5b6472",
};

Chart.defaults.font.family = "'Segoe UI', 'Malgun Gothic', -apple-system, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = PV.chartPalette.text;
Chart.defaults.borderColor = PV.chartPalette.grid;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
