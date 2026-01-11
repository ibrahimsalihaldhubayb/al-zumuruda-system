import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعداد Firebase مع الذاكرة المؤقتة ---
@st.cache_resource
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

# --- 2. دالة قراءة الـ PDF المسرعة (تحفظ البيانات في الذاكرة) ---
@st.cache_data
def load_all_units_from_pdf(path):
    units = {}
    if os.path.exists(path):
        with pdfplumber.open(path) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            units[uid] = {
                                'id': uid,
                                'blk': r[1],
                                'area': r[4],
                                'price': "".join(re.findall(r'\d+', str(r[6]))) if r[6] else "0",
                                'status': 'متاح'
                            }
    return units

def format_money_en(amount):
    return "{:,.2f}".format(amount).replace('٫', '.').replace('٬', ',')

Z_COPPER = "#BC846C" 
Z_DARK = "#1B3022" 
Z_LIGHT = "#F4F1EE"

# --- 3. نظام الأمان ---
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

# --- 4. محرك الوورد ---
def create_word_offer(data, cust_name, net_p):
    try:
        current_dir = os.getcwd()
        template_path = os.path.join(current_dir, "Projecttemmplate.docx")
        if not os.path.exists(template_path):
            alt = glob.glob(os.path.join(current_dir, "Project*.docx"))
            if alt: template_path = alt[0]
            else: return None

        doc = DocxTemplate(template_path)
        office_fees = 2000.00 
        total_with_fees = net_p + office_fees
        
        context = {
            'date': datetime.now().strftime("%Y/%m/%d"),
            'name': str(cust_name),
            'id': str(data['id']),
            'blk': str(data['blk']),
            'area': str(data['area']),
            'price': str(format_money_en(net_p)), 
            'fees': str(format_money_en(office_fees)),
            'total': str(format_money_en(total_with_fees)),
            'desc': f"بلك: {data['blk']} - مساحة: {data['area']} م²"
        }
        doc.render(context)
        out_io = io.BytesIO()
        doc.save(out_io)
        return out_io.getvalue()
    except: return None

# --- الواجهة الرئيسية ---
if check_password():
    st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")
    st.markdown(f"""<style>@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap');* {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif !important; }} .stApp {{ background-color: {Z_LIGHT}; }} .modern-card {{ background: white; padding: 30px; border-radius: 20px; border-right: 15px solid {Z_COPPER}; box-shadow: 10px 10px 30px rgba(0,0,0,0.05); margin-bottom: 30px; }} .highlight-val {{ color: {Z_COPPER} !important; font-size: 24px !important; font-weight: 800 !important; }} .stDownloadButton>button {{ background: linear-gradient(135deg, {Z_COPPER} 0%, #a6735d 100%) !important; color: white !important; width: 100% !important; height: 60px !important; border-radius: 15px !important; font-size: 20px !important; border: none !important; }}</style>""", unsafe_allow_html=True)

    st.markdown("<h1 style='text-align:center; color:#1B3022;'>🏛️ بوابة مبيعات مشروع الزمردة</h1>", unsafe_allow_html=True)
    
    # تحميل البيانات مرة واحدة فقط عند تشغيل التطبيق
    pdf_path = "الوحدات الشاغرة في مشروع الزمردة حتى تاريخ 28-12-2025.pdf"
    all_units = load_all_units_from_pdf(pdf_path)

    tab1, tab2 = st.tabs(["💎 المبيعات", "⚙️ السحابة"])

    with tab1:
        c1, c2, c3 = st.columns([1,2,1])
        with c2: search_id = st.text_input("🔍 ادخل رقم القطعة للبحث السريع:")
        
        if search_id:
            uid = str(search_id).strip()
            res = None
            
            # البحث في السحابة أولاً (أسرع)
            if db:
                doc_cloud = db.collection('units').document(uid).get()
                if doc_cloud.exists: res = doc_cloud.to_dict()
            
            # إذا لم تكن في السحابة، ابحث في الذاكرة (التي قرأت من الـ PDF)
            if not res and uid in all_units:
                res = all_units[uid]

            if res:
                st.markdown(f"<div class='modern-card'><h2 style='color:#1B3022;'>القطعة رقم {res['id']} ({res['status']})</h2><hr><div style='display:grid; grid-template-columns: 1fr 1fr 1fr; text-align:center;'><div><p>رقم البلك</p><b class='highlight-val'>{res['blk']}</b></div><div><p>المساحة</p><b class='highlight-val'>{res['area']} م²</b></div><div><p>السعر الأساسي</p><b class='highlight-val'>{format_money_en(float(res['price']))}</b></div></div></div>", unsafe_allow_html=True)
                
                if res['status'] == "متاح":
                    col1, col2 = st.columns(2)
                    c_name = col1.text_input("👤 اسم العميل الموقر:")
                    disc = col2.number_input("📉 نسبة الخصم (%):", 0.0, 100.0, 0.0)
                    final_p = float(res['price']) * (1 - disc/100)
                    
                    st.markdown(f"<h3 style='text-align:center; color:{Z_COPPER};'>الصافي: {format_money_en(final_p)} ريال</h3>", unsafe_allow_html=True)
                    
                    if c_name:
                        word_file = create_word_offer(res, c_name, final_p)
                        if word_file:
                            st.download_button("📥 تحميل عرض السعر", data=word_file, file_name=f"عرض_{c_name}.docx")
            else: st.error("مباعة قد تحتاج بحث وتعديل بالسحابه")
                
