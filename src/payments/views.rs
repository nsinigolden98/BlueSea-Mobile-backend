//! View handlers for the payments app (mirrors `payments/views.py`),
//! split by concern:
//!   airtime.rs     <-> AirtimeTopUpViews
//!   data.rs        <-> MTN/Airtel/Glo/9mobile data views
//!   cable.rs       <-> DSTV/GOTV/Startimes/ShowMax views
//!   electricity.rs <-> ElectricityPaymentViews
//!   exam.rs        <-> WAEC registration/result + JAMB views
//!   customer.rs    <-> ElectricityPaymentCustomerViews
//!   group.rs       <-> GroupPaymentViews + GroupPaymentHistory
//!   internal.rs    <-> InternalTransferView
//!   withdrawal.rs  <-> WithdrawalView
//!   status.rs      <-> PaymentStatusView
//!   common.rs      <-> PIN gate, descriptions, settle tail

pub mod airtime;
pub mod betting;
pub mod cable;
pub mod common;
pub mod customer;
pub mod data;
pub mod electricity;
pub mod exam;
pub mod group;
pub mod internal;
pub mod status;
pub mod withdrawal;
