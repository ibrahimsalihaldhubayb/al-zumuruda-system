import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعداد Firebase ---
def init_firebase():
    if not firebase_admin._apps:
        try:
            cred_path = 'firebase_key.json'
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                return firestore.client()
            return None
        except: return None
    else: return firestore.client()

db = init_firebase()

def extract_price(price_val):
    if not price_val: return 0.0
    num = "".join(re.findall(r'\d+', str(price_val)))
    return float(num) if num else 0.0

# دالة التنسيق المالي (إجبار التنسيق الإنجليزي)
def format_money_en(amount):
    # استخدام التنسيق اللاتيني الصريح لضمان الأرقام الإنجليزية
    return "{:,.2f}".format(amount).replace('٫', '.').replace('٬', ',')

Z_COPPER = "#BC846C" 
Z_DARK = "#1B3022" 
Z_LIGHT = "#F4F1EE"

# --- 2. نظام الأمان ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown(f"<div style='text-align: center; padding: 100px 20px;'><h1 style='color: {Z_DARK}; font-size: 50px;'>🏛️ الزمردة العقارية</h1></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,1.5,1])
        with c2:
            pwd = st.text_input("مفتاح الدخول للنظام:", type="password")
            if st.button("🔐 دخول آمن"):
                if pwd == "Alaqtar2026":
                    st.session_state["password_correct"] = True
                    st.rerun()
        return False
    return True

# --- 3. محرك الوورد (تثبيت الأرقام الإنجليزية) ---
def create_word_offer(data, cust_name, net_p):
    try:
        current_dir = os.getcwd()
        template_path = os.path.join(current_dir, "Projecttemmplate.docx")
        
        if not os.path.exists(template_path):
            alternative = glob.glob(os.path.join(current_dir, "Project*.docx"))
            if alternative: template_path = alternative[0]
            else: return None

        doc = DocxTemplate(template_path)
        
        office_fees = 2000.00 
        total_with_fees = net_p + office_fees
        
        auto_desc = f"بلك: {data['blk']} - مساحة: {data['area']} م²"
        
        # نرسل الأرقام كـ "نصوص" لضمان عدم تغير شكلها في الوورد
        context = {
            'date': datetime.now().strftime("%Y/%m/%d"),
            'name': str(cust_name),
            'id': str(data['id']),
            'blk': str(data['blk']),
            'area': str(data['area']),
            'price': str(format_money_en(net_p)), 
            'fees': str(format_money_en(office_fees)),
            'total': str(format_money_en(total_with_fees)),
            'desc': auto_desc
        }
        
        doc.render(context)
        out_io = io.BytesIO()
        doc.save(out_io)
        return out_io.getvalue()
    except: return None

# --- 4. الواجهة الرئيسية ---
if check_password():
    st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")
    st.markdown(f"""<style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap');* {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif !important; }} .stApp {{ background-color: {Z_LIGHT}; }} label, .stMarkdown p {{ color: {Z_COPPER} !important; font-weight: bold !important; font-size: 18px !important; }} .modern-card {{ background: white; padding: 30px; border-radius: 20px; border-right: 15px solid {Z_COPPER}; box-shadow: 10px 10px 30px rgba(0,0,0,0.05); margin-bottom: 30px; }} .highlight-val {{ color: {Z_COPPER} !important; font-size: 24px !important; font-weight: 800 !important; }} .stDownloadButton {{ display: flex; justify-content: center; padding-top: 20px; }} .stDownloadButton>button {{ background: linear-gradient(135deg, {Z_COPPER} 0%, #a6735d 100%) !important; color: white !important; width: 80% !important; height: 65px !important; border-radius: 15px !important; font-size: 22px !important; font-weight: bold !important; border: none !important; }}</style>""", unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#1B3022;'>🏛️ بوابة مبيعات مشروع الزمردة</h1>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["💎 المبيعات", "⚙️ السحابة"])

    with tab1:
        c1, c2, c3 = st.columns([1,2,1])
        with c2: search_id = st.text_input("🔍 ابحث عن رقم القطعة:")
        
        if search_id:
            uid = str(search_id).strip()
            res = None
            if db:
                doc_cloud = db.collection('units').document(uid).get()
                if doc_cloud.exists: res = doc_cloud.to_dict()
            
            if not res:
                path = "الوحدات الشاغرة في مشروع الزمردة حتى تاريخ 28-12-2025.pdf"
                if os.path.exists(path):
                    with pdfplumber.open(path) as p:
                        for page in p.pages:
                            table = page.extract_table()
                            if table:
                                for r in table[1:]:
                                    if r and r[0] and str(r[0]).strip() == uid:
                                        res = {'id': r[0], 'blk': r[1], 'area': r[4], 'price': extract_price(r[6]), 'status': 'متاح'}
                                        break
            if res:
                st.markdown(f"<div class='modern-card'><h2 style='color:#1B3022;'>القطعة رقم {res['id']} ({res['status']})</h2><hr><div style='display:grid; grid-template-columns: 1fr 1fr 1fr; text-align:center;'><div><p>رقم البلك</p><b class='highlight-val'>{res['blk']}</b></div><div><p>المساحة</p><b class='highlight-val'>{res['area']} م²</b></div><div><p>السعر الأساسي</p><b class='highlight-val'>{format_money_en(float(res['price']))}</b></div></div></div>", unsafe_allow_html=True)
                
                if res['status'] == "متاح":
                    col1, col2 = st.columns(2)
                    c_name = col1.text_input("👤 اسم العميل الموقر:")
                    disc = col2.number_input("📉 نسبة الخصم (%):", 0.0, 100.0, 0.0)
                    final_p = float(res['price']) * (1 - disc/100)
                    
                    st.markdown(f"<h3 style='text-align:center; color:{Z_COPPER};'>الصافي قبل الرسوم: {format_money_en(final_p)} ريال</h3>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center; color:{Z_DARK};'>الإجمالي (شامل الرسوم): {format_money_en(final_p + 2000)} ريال</h3>", unsafe_allow_html=True)
                    
                    if c_name:
                        word_data = create_word_offer(res, c_name, final_p)
                        if word_data:
                            st.download_button(
                                label="✨ استخراج وتحميل عرض السعر الفاخر ✨",
                                data=word_data,
                                file_name=f"عرض_الزمردة_{c_name}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
            else: st.error("❌ غير موجود")

    with tab2:
        st.markdown("<div class='modern-card'><h3>⚙️ تعديل السحابة</h3></div>", unsafe_allow_html=True)
        if db:
            edit_id = st.text_input("رقم القطعة للتعديل:")
            if edit_id:
                curr = db.collection('units').document(edit_id).get()
                curr_data = curr.to_dict() if curr.exists else {}
                with st.form("cloud_form"):
                    e_blk = st.text_input("رقم البلك:", value=curr_data.get('blk', ''))
                    e_area = st.text_input("المساحة:", value=curr_data.get('area', ''))
                    e_price = st.number_input("السعر:", value=float(curr_data.get('price', 0)))
                    e_status = st.selectbox("الحالة:", ["متاح", "محجوز", "مباع"], index=0 if curr_data.get('status') == "متاح" else 1)
                    if st.form_submit_button("💾 حفظ البيانات"):
                        db.collection('units').document(edit_id).set({'id': edit_id, 'blk': e_blk, 'area': e_area, 'price': e_price, 'status': e_status})
                        st.success("✅ تم التحديث!")