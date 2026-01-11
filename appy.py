import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. إعدادات المظهر ---
st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")
Z_COPPER, Z_DARK, Z_LIGHT = "#BC846C", "#1B3022", "#F4F1EE"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    * {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif; color: {Z_DARK}; }}
    .stApp {{ background-color: {Z_LIGHT}; }}
    .card {{ background: white; padding: 20px; border-radius: 12px; border-right: 10px solid {Z_COPPER}; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
    .val {{ color: {Z_COPPER} !important; font-weight: bold; font-size: 20px; }}
    </style>
""", unsafe_allow_html=True)

# --- 2. إعداد السحابة ---
@st.cache_resource
def init_firebase():
    try:
        if not firebase_admin._apps:
            if os.path.exists('firebase_key.json'):
                cred = credentials.Certificate('firebase_key.json')
                firebase_admin.initialize_app(cred)
        return firestore.client()
    except: return None

db = init_firebase()

# --- 3. معالجة الملفات (تحميل شامل وسريع) ---
@st.cache_data(show_spinner="⚡ جاري تحميل بيانات المخطط والوحدات...")
def load_all_data():
    master_data = {} # يحتوي كل قطع المخطط
    
    # أ. قراءة ملف "نموذج المخطط" (الأساس)
    master_files = glob.glob("*نموذج المخطط*.pdf")
    if master_files:
        with pdfplumber.open(master_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            price_raw = "".join(re.findall(r'\d+', str(r[6]))) if len(r)>6 else "0"
                            master_data[uid] = {
                                'id': uid, 'blk': r[1], 'area': r[4],
                                'price': float(price_raw) if price_raw else 0.0,
                                'status': 'مباع' # الافتراضي مباع حتى نجدها في الشاغر
                            }
    
    # ب. قراءة ملف "الوحدات الشاغرة" لتحديث الحالة لـ "متاح"
    vacant_files = glob.glob("*الشاغرة*.pdf")
    if vacant_files:
        with pdfplumber.open(vacant_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            if uid in master_data:
                                master_data[uid]['status'] = 'متاح'
    return master_data

all_units = load_all_data()

# --- 4. واجهة المستخدم ---
st.title("🏛️ نظام مبيعات الزمردة المتكامل")

tab1, tab2 = st.tabs(["💎 محرك البحث", "⚙️ تحديث السحابة"])

with tab1:
    search_id = st.text_input("🔍 ادخل رقم القطعة:")
    if search_id:
        uid = str(search_id).strip()
        if uid in all_units:
            unit = all_units[uid]
            
            # جلب الحالة من السحابة (تغطي على الـ PDF)
            current_status = unit['status']
            if db:
                try:
                    doc = db.collection('units').document(uid).get(timeout=1)
                    if doc.exists: current_status = doc.to_dict().get('status', current_status)
                except: pass

            color = "#28a745" if current_status == "متاح" else "#dc3545"
            st.markdown(f"""
            <div class="card">
                <h3>قطعة رقم {unit['id']} <span style="color:{color}">({current_status})</span></h3>
                <p>بلك: <span class="val">{unit['blk']}</span> | مساحة: <span class="val">{unit['area']} م²</span></p>
                <p>السعر: <span class="val">{unit['price']:,} ريال</span></p>
            </div>
            """, unsafe_allow_html=True)

            if current_status == "متاح":
                st.write("---")
                c1, c2 = st.columns(2)
                c_name = c1.text_input("👤 اسم العميل:")
                discount = c2.number_input("📉 خصم %:", 0.0, 100.0, 0.0)
                
                final_p = unit['price'] * (1 - discount/100)
                if c_name and st.button("📄 إصدار العرض"):
                    # كود الوورد
                    doc_path = "projecttemplate.docx"
                    if os.path.exists(doc_path):
                        tpl = DocxTemplate(doc_path)
                        tpl.render({'date': datetime.now().strftime("%Y/%m/%d"), 'name': c_name, 'id': unit['id'], 'blk': unit['blk'], 'area': unit['area'], 'price': f"{final_p:,.2f}", 'total': f"{final_p+2000:,.2f}", 'fees': "2,000.00", 'desc': f"قطعة {unit['id']} بلك {unit['blk']}"})
                        out = io.BytesIO(); tpl.save(out)
                        st.download_button(f"📥 تحميل عرض {c_name}", out.getvalue(), f"عرض_{c_name}.docx")
        else:
            st.error("❌ هذه القطعة غير موجودة في المخطط.")

with tab2:
    st.subheader("تحديث حالة القطع")
    if db:
        u_id = st.text_input("رقم القطعة:")
        n_status = st.selectbox("الحالة الجديدة:", ["متاح", "مباع", "محجوز"])
        if st.button("حفظ التغيير"):
            db.collection('units').document(u_id).set({'status': n_status}, merge=True)
            st.success(f"تم تحديث القطعة {u_id} إلى {n_status} بنجاح!")
            st.cache_data.clear() # لمسح الكاش وتحديث البيانات فوراً
