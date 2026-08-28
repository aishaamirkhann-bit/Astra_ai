// Backend already sends pre-formatted "Rs. 134,999" strings for most display
// fields (price_display, available_balance_display). This is only for the
// few raw numbers that come back without a display string, like Goal
// target/allocated/remaining amounts.
export function formatPkr(amount: number): string {
  return `Rs. ${Math.round(amount).toLocaleString("en-PK")}`;
}
