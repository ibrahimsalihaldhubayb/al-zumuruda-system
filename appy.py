import streamlit as st
import pdfplumber
import os, re, io, glob
from datetime import datetime
from docxtpl import DocxTemplate
import firebase_admin
from firebase_admin import credentials, firestore

# --- الإعدادات الفنية الفخمة ---
st.set_page_config(page_title="شركة الاقطار للتطوير العقاري نظام المبيعات", layout="wide")

# --- محرك السرعة القصوى (التحميل المسبق) ---
@st.cache_data(show_spinner="⚡ يتم الآن معالجة البيانات لضمان سرعة البحث...")
def get_master_data():
    full_inventory = {}
    
    # 1. قراءة المخطط العام (الأساس)
    master_files = glob.glob("*نموذج المخطط*.pdf")
    if master_files:
        with pdfplumber.open(master_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            price = "".join(re.findall(r'\d+', str(r[6]))) if len(r)>6 else "0"
                            full_inventory[uid] = {
                                'id': uid, 'blk': r[1], 'area': r[4],
                                'price': float(price) if price else 0.0,
                                'status': 'مباع'
                            }
    
    # 2. قراءة الشواغر لتحديث الحالة
    vacant_files = glob.glob("*الشاغرة*.pdf")
    if vacant_files:
        with pdfplumber.open(vacant_files[0]) as p:
            for page in p.pages:
                table = page.extract_table()
                if table:
                    for r in table[1:]:
                        if r and r[0]:
                            uid = str(r[0]).strip()
                            if uid in full_inventory:
                                full_inventory[uid]['status'] = 'متاح'
    return full_inventory

# تحميل البيانات للذاكرة (يتم مرة واحدة فقط لكل الموظفين)
cached_data = get_master_data()

# --- واجهة المستخدم ---
st.title("🏛️ بوابة مبيعات الزمردة - النسخة السريعة")

# خانة البحث (الآن سريعة جداً)
search_id = st.text_input("🔍 ادخل رقم القطعة:")

if search_id:
    uid = search_id.strip()
    if uid in cached_data:
        unit = cached_data[uid]
        
        # عرض البيانات فوراً
        st.success(f"تم العثور على القطعة {uid}")
        st.write(f"الحالة: **{unit['status']}** | السعر: **{unit['price']:,} ريال**")
        
        if unit['status'] == 'متاح':
            # الحاسبة وبقية المهام...
            pass
    else:
        st.error("القطعة غير موجودة في المخطط العام.")

# زر لإعادة تحميل الملفات في حال قمت برفع ملفات جديدة
if st.sidebar.button("🔄 تحديث قاعدة البيانات من الملفات"):
    st.cache_data.clear()
    st.rerun()

