type Column<T> = {
  key: keyof T;
  label: string;
  align?: "left" | "right" | "center";
};

type DataTableProps<T> = {
  columns: Column<T>[];
  rows: T[];
  emptyText?: string;
};

export default function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  emptyText = "No data",
}: DataTableProps<T>) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={String(col.key)} style={{ textAlign: col.align || "left" }}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="table-empty">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row, idx) => (
              <tr key={idx}>
                {columns.map((col) => (
                  <td key={String(col.key)} style={{ textAlign: col.align || "left" }}>
                    {String(row[col.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
