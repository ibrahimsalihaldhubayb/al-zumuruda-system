import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- 1. التنسيق والواجهة الفخمة ---
Z_COPPER, Z_DARK, Z_LIGHT = "#BC846C", "#1B3022", "#F4F1EE"
st.set_page_config(page_title="نظام الزمردة العقاري", layout="wide")

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap');
    * {{ direction: RTL; text-align: right; font-family: 'Cairo', sans-serif; }}
    .stApp {{ background-color: {Z_LIGHT}; }}
    h1, h2, h3, p, span, label, .stMarkdown {{ color: {Z_DARK} !important; }}
    .main-card {{ background: white; padding: 25px; border-radius: 15px; border-right: 12px solid {Z_COPPER}; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 20px; }}
    .val-box {{ color: {Z_COPPER} !important; font-size: 24px; font-weight: 800; }}
    .stTabs [data-baseweb="tab"] p {{ color: {Z_DARK} !important; font-weight: bold; }}
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

# --- 3. محرك البحث الذكي (شاغر أولاً ثم مخطط) ---
@st.cache_data(show_spinner="جاري تحديث البيانات...")
def load_and_index_data():
    inventory = {}
    
    # أ. قراءة ملف "نموذج المخطط" كقاعدة بيانات شاملة
    master_files = glob.glob("*نموذج المخطط*.pdf")
    if master_files:
        with pdfplumber.open(master_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and len(r) > 0 and r[0]:
                            uid = str(r[0]).strip()
                            price_raw = "".join(re.findall(r'\d+', str(r[6]))) if len(r)>6 and r[6] else "0"
                            inventory[uid] = {
                                'id': uid, 'blk': r[1], 'area': r[4],
                                'price': float(price_raw) if price_raw else 0.0,
                                'status': 'مباع' # الافتراضي لكل المخطط أنه مباع
                            }
    
    # ب. قراءة ملف "الشاغرة" وتحديث الحالة لـ "متاح"
    vacant_files = glob.glob("*الشاغرة*.pdf")
    if vacant_files:
        with pdfplumber.open(vacant_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and len(r) > 0 and r[0]:
                            uid = str(r[0]).strip()
                            # إذا كانت في الشاغر، نحدث حالتها أو نضيفها لو لم تكن في المخطط
                            if uid in inventory:
                                inventory[uid]['status'] = 'متاح'
                            else:
                                # في حال وجود قطعة في الشاغر وليست في ملف المخطط
                                price_raw = "".join(re.findall(r'\d+', str(r[6]))) if len(r)>6 and r[6] else "0"
                                inventory[uid] = {
                                    'id': uid, 'blk': r[1], 'area': r[4],
                                    'price': float(price_raw) if price_raw else 0.0,
                                    'status': 'متاح'
                                }
    return inventory

units_data = load_and_index_data()

# --- 4. واجهة البحث ---
st.markdown(f"<h1 style='text-align:center;'>🏛️ بوابة مبيعات مشروع الزمردة</h1>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["💎 محرك البحث", "⚙️ الإدارة"])

with tab1:
    search_id = st.text_input("🔍 ادخل رقم القطعة للبحث:")
    if search_id:
        uid = str(search_id).strip()
        
        if uid in units_data:
            unit = units_data[uid]
            status = unit['status']
            
            # جلب الحالة من السحابة (الأولوية القصوى)
            if db:
                try:
                    doc = db.collection('units').document(uid).get(timeout=1)
                    if doc.exists: status = doc.to_dict().get('status', status)
                except: pass

            # تنسيق العرض حسب الحالة
            st_color = "#28a745" if status == "متاح" else "#dc3545"
            st.markdown(f"""
            <div class="main-card">
                <h2 style="margin-bottom:20px;">تفاصيل القطعة {unit['id']} <span style="color:{st_color};">({status})</span></h2>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                    <div><span style="opacity:0.7;">رقم البلك:</span><br><span class="val-box">{unit['blk']}</span></div>
                    <div><span style="opacity:0.7;">المساحة:</span><br><span class="val-box">{unit['area']} م²</span></div>
                    <div><span style="opacity:0.7;">السعر الأساسي:</span><br><span class="val-box">{unit['price']:,.2f} ريال</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if status == "متاح":
                st.write("---")
                col1, col2 = st.columns(2)
                c_name = col1.text_input("👤 اسم العميل:")
                disc = col2.number_input("📉 نسبة الخصم %:", 0.0, 100.0, 0.0)
                
                f_price = unit['price'] * (1 - disc/100)
                total = f_price + 2000
                st.info(f"الصافي بعد الخصم: {f_price:,.2f} ريال | الإجمالي مع السعي: {total:,.2f} ريال")
                
                if c_name and st.button("📄 إصدار عرض السعر"):
                    if os.path.exists("projecttemplate.docx"):
                        tpl = DocxTemplate("projecttemplate.docx")
                        tpl.render({
                            'date': datetime.now().strftime("%Y/%m/%d"), 'name': c_name,
                            'id': unit['id'], 'blk': unit['blk'], 'area': unit['area'],
                            'price': f"{f_price:,.2f}", 'fees': "2,000.00", 'total': f"{total:,.2f}",
                            'desc': f"قطعة {unit['id']} بلك {unit['blk']}"
                        })
                        out = io.BytesIO(); tpl.save(out)
                        st.download_button(f"📥 تحميل العرض", out.getvalue(), f"عرض_{c_name}.docx")
            else:
                st.warning("⚠️ هذه القطعة مباعة حالياً ولا يمكن إصدار عرض سعر لها.")
        else:
            st.error("❌ عذراً، رقم هذه القطعة غير موجود في السجلات (تأكد من الرقم).")

with tab2:
    st.subheader("تحديث حالة القطع سحابياً")
    if db:
        u_id = st.text_input("رقم القطعة:")
        n_st = st.selectbox("الحالة الجديدة:", ["متاح", "مباع", "محجوز"])
        if st.button("تحديث السحابة"):
            db.collection('units').document(str(u_id)).set({'status': n_st}, merge=True)
            st.success(f"تم تحديث {u_id} بنجاح")
            st.cache_data.clear()
