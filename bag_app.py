import streamlit as st
import sqlite3
import pandas as pd
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os

# --- CONFIGURATION ---
DB_FILE = 'bag_maker.db'
LOW_STOCK_THRESHOLD = 5
CATEGORIES = ["", "Fabric", "Hardware", "Zipper", "Interfacing", "Thread", "Webbing"]
COLORS = ["", "Nickel", "Antique Brass", "Gold", "Rose Gold", "Black", "Rainbow", "Natural"]

# --- DATABASE FUNCTIONS ---
def run_query(query, params=()):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

def get_df(query):
    with sqlite3.connect(DB_FILE) as conn:
        return pd.read_sql_query(query, conn)

# Initialize Database Table
run_query('''CREATE TABLE IF NOT EXISTS inventory 
             (id INTEGER PRIMARY KEY, part_number TEXT, name TEXT, category TEXT,
              color TEXT, qty INTEGER, cost REAL, price REAL)''')

# --- PDF GENERATOR ---
def create_pdf(data_list, title, filename, is_invoice=True):
    pdf = FPDF()
    pdf.add_page()
    
    # --- LOGO & BUSINESS INFO ---
    # To use a logo, uncomment the line below and ensure 'logo.png' is in your folder
    pdf.image('logo.png', 10, 8, 33) 
    
    pdf.set_font("Helvetica", 'B', 20)
    pdf.cell(0, 10, "SWaG Bag", ln=True, align='R') # Change to your business name
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 5, "627 Mile Creek Rd, Edgemoor, SC 29712", ln=True, align='R')
    pdf.cell(0, 5, "Email: sheldon.gilreath@gmail.com", ln=True, align='R')
    pdf.ln(10)
    
    # --- TITLE ---
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, title, ln=True, align='L')
    pdf.set_font("Helvetica", size=10)
    pdf.ln(5)
    
    # --- TABLE HEADER ---
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(240, 240, 240) # Light gray background for headers
    cols = ["SKU", "Item Name", "Color", "Qty"]
    if is_invoice: cols.append("Total")
    
    for col in cols:
        w = 70 if col == "Item Name" else 30
        pdf.cell(w, 10, col, border=1, fill=True)
    pdf.ln()
    
    # --- TABLE ROWS ---
    pdf.set_font("Helvetica", size=10)
    grand_total = 0
    for item in data_list:
        pdf.cell(30, 10, str(item['part_number']), border=1)
        pdf.cell(70, 10, item['name'], border=1)
        pdf.cell(30, 10, str(item['color']), border=1)
        pdf.cell(30, 10, str(item['qty']), border=1)
        if is_invoice:
            pdf.cell(30, 10, f"${item['total']:.2f}", border=1)
            grand_total += item['total']
        pdf.ln()
    
    if is_invoice:
        pdf.ln(5)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(160, 10, "GRAND TOTAL: ", border=0, align='R')
        pdf.cell(30, 10, f"${grand_total:.2f}", border=0)
        
        pdf.ln(20)
        pdf.set_font("Helvetica", 'I', 10)
        pdf.cell(0, 10, "Thank you for supporting my handmade business!", ln=True, align='C')
    
    pdf.output(filename)
    return filename

# --- UI SETUP ---
st.set_page_config(page_title="Bag Maker Pro", layout="wide")

# Persistent Sidebar Data
df_all = get_df("SELECT * FROM inventory")

st.sidebar.title("👜 Bag Maker Pro")
low_stock_items = df_all[df_all['qty'] <= LOW_STOCK_THRESHOLD]
if not low_stock_items.empty:
    st.sidebar.error("⚠️ LOW STOCK ALERT")
    st.sidebar.dataframe(low_stock_items[['part_number', 'qty']], hide_index=True)
else:
    st.sidebar.success("✅ Stock Levels OK")

menu = ["Inventory Manager", "Create Pull List & Invoice"]
choice = st.sidebar.selectbox("Navigation", menu)

# --- SECTION 1: INVENTORY MANAGER ---
if choice == "Inventory Manager":
    st.header("📦 Parts Inventory Manager")
    
    col_add, col_edit = st.columns(2)
    
    with col_add:
        st.subheader("Add New Part")
        with st.form("add_form", clear_on_submit=True):
            p_num = st.text_input("Part Number / SKU")
            p_name = st.text_input("Part Name")
            p_cat = st.selectbox("Category", CATEGORIES)
            p_col = st.selectbox("Color/Finish", COLORS)
            p_qty = st.number_input("Initial Quantity", min_value=0)
            p_cost = st.number_input("Your Cost (per unit)", min_value=0.0)
            p_price = st.number_input("Retail Price (per unit)", min_value=0.0)
            
            if st.form_submit_button("Save New Item"):
                run_query("INSERT INTO inventory (part_number, name, category, color, qty, cost, price) VALUES (?,?,?,?,?,?,?)", 
                          (p_num, p_name, p_cat, p_col, p_qty, p_cost, p_price))
                st.success("New item added!")
                st.rerun()

    with col_edit:
        st.subheader("Edit / Restock Existing Part")
        if not df_all.empty:
            df_all['edit_display'] = df_all['part_number'] + " (" + df_all['name'] + ")"
            selected_edit = st.selectbox("Select Part to Update", df_all['edit_display'].tolist())
            
            # Get current data for selection
            part_data = df_all[df_all['edit_display'] == selected_edit].iloc[0]
            
            with st.form("edit_form"):
                u_qty = st.number_input("Current Stock Count", value=int(part_data['qty']))
                u_cost = st.number_input("Current Cost", value=float(part_data['cost']))
                u_price = st.number_input("Current Price", value=float(part_data['price']))
                
                if st.form_submit_button("Apply Changes"):
                    run_query("UPDATE inventory SET qty = ?, cost = ?, price = ? WHERE id = ?", 
                              (u_qty, u_cost, u_price, int(part_data['id'])))
                    st.success("Item updated!")
                    st.rerun()
        else:
            st.info("No items in database to edit.")

    st.divider()
    st.subheader("Current Inventory Table")
    st.dataframe(df_all.drop(columns=['edit_display'], errors='ignore'), use_container_width=True, hide_index=True)
    
    if not df_all.empty:
        csv = df_all.drop(columns=['edit_display'], errors='ignore').to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export to Excel (CSV)", csv, "bag_inventory.csv", "text/csv")

# --- SECTION 2: PULL LIST & INVOICE ---
else:
    st.header("📋 Pull List & Billing")
    
    # Initialize session states
    if 'pull_list' not in st.session_state: st.session_state.pull_list = []
    if 'current_invoice_file' not in st.session_state: st.session_state.current_invoice_file = None

    if not df_all.empty:
        df_all['display'] = df_all['part_number'].astype(str) + " - " + df_all['name'] + " (" + df_all['color'].astype(str) + ")"
        
        col_setup, col_list = st.columns([1, 1])
        
        with col_setup:
            customer = st.text_input("Customer Name", "Retail Customer")
            cust_email = st.text_input("Customer Email")
            selected_item = st.selectbox("Select Part", df_all['display'].tolist())
            p_qty = st.number_input("Quantity to Pull", min_value=1)
            
            if st.button("➕ Add to Pull List"):
                item_data = df_all[df_all['display'] == selected_item].iloc[0]
                st.session_state.pull_list.append({
                    "part_number": item_data['part_number'], "name": item_data['name'],
                    "color": item_data['color'], "qty": p_qty,
                    "price": item_data['price'], "total": p_qty * item_data['price'], "id": int(item_data['id'])
                })
                st.rerun()

        with col_list:
            if st.session_state.pull_list:
                st.subheader("Items in Current List")
                st.table(pd.DataFrame(st.session_state.pull_list)[['part_number', 'name', 'qty', 'total']])
                if st.button("Clear List"):
                    st.session_state.pull_list = []
                    st.rerun()

        if st.session_state.pull_list:
            st.divider()
            c1, c2 = st.columns(2)
            
            with c1:
                if st.button("🖨️ Generate Pull List (For Workshop)"):
                    fn = create_pdf(st.session_state.pull_list, "WORKSHOP PULL LIST", "pull_list.pdf", False)
                    with open(fn, "rb") as f:
                        st.download_button("Download Pull List PDF", f, file_name=fn)

            with c2:
                if st.button("📄 Finalize & Deduct Stock"):
                    # 1. Update Database
                    for item in st.session_state.pull_list:
                        run_query("UPDATE inventory SET qty = qty - ? WHERE id = ?", (item['qty'], item['id']))
                    # 2. Generate PDF
                    inv_fn = create_pdf(st.session_state.pull_list, f"INVOICE: {customer}", f"invoice_{customer.replace(' ','_')}.pdf")
                    st.session_state.current_invoice_file = inv_fn
                    st.session_state.pull_list = [] # Reset list
                    st.success("Inventory updated and Invoice generated!")
                    st.rerun()

        # Email and Download section after Finalizing
        if st.session_state.current_invoice_file:
            st.divider()
            st.subheader("✅ Actions for Generated Invoice")
            ca, cb = st.columns(2)
            with ca:
                with open(st.session_state.current_invoice_file, "rb") as f:
                    st.download_button("💾 Download/Print Invoice", f, file_name=st.session_state.current_invoice_file)
            with cb:
                if st.button("📧 Send Email via Gmail"):
                    try:
                        user = st.secrets["EMAIL_USER"]
                        pw = st.secrets["EMAIL_PASS"]
                        
                        msg = MIMEMultipart()
                        msg['From'], msg['To'], msg['Subject'] = user, cust_email, f"Invoice for {customer}"
                        msg.attach(MIMEText("Hello, please find your bag parts invoice attached."))
                        
                        with open(st.session_state.current_invoice_file, "rb") as attachment:
                            p = MIMEBase('application', 'octet-stream')
                            p.set_payload(attachment.read()); encoders.encode_base64(p)
                            p.add_header('Content-Disposition', f"attachment; filename= {st.session_state.current_invoice_file}")
                            msg.attach(p)
                        
                        s = smtplib.SMTP('smtp.gmail.com', 587)
                        s.starttls(); s.login(user, pw)
                        s.send_message(msg); s.quit()
                        st.success("✅ Email Sent!")
                        st.session_state.current_invoice_file = None # Reset state
                    except Exception as e:
                        st.error(f"Email failed. Ensure .streamlit/secrets.toml is correct. Error: {e}")
    else:
        st.info("Add parts to your inventory to get started.")