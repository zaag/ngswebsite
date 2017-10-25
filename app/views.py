import os
import json
import sys
from collections import OrderedDict

from flask import render_template, flash, redirect, url_for, request, send_from_directory
from werkzeug.utils import secure_filename

from app import app

sys.path.insert(0, os.path.join(os.path.expanduser('~'), 'Documents', 'ngsscriptlibrary'))

from ngsscriptlibrary import TargetDatabase, TargetFiles, TargetAnnotation, SampleSheet

TARGETS = '/home/manager/Documents/ngstargets/'
DB = '/home/manager/Documents/ngstargets/varia/capinfo.sqlite'

def boolean_to_number(x):
    if x == 'False':
        x = 0
    elif not x:
        x = 0
    elif x == 'True':
        x = 1
    elif x:
        x = 1
    return x

@app.route('/')
@app.route('/index/')
def intro():
    return render_template('index.html')

@app.route('/diagnostiek/')
def show_all_tests():
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    tests.sort()
    d = OrderedDict()
    for test in tests:
        d[test] = T.get_active_capture_for_test(test)
    return render_template('showalltests.html', tests=d)


@app.route('/diagnostiek/<test>')
def show_testinfo(test):
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    if test not in tests:
        flash('Niet gevonden')
        return redirect(url_for('show_all_tests'))
    caps = T.get_all_captures_for_test(test)

    d = T.get_all_info_for_test(test)

    for i in ['printcnv', 'mozaiekdetectie']:
        if d['capdb'][i] == 1:
            d['capdb'][i] = 'Ja'
        elif d['capdb'][i] == 0:
            d['capdb'][i] = 'Nee'
    if d['genes']['panelsize'] is None:
        d['genes']['panelsize'] = 0
    if d['capdb']['panel'] == 'False':
        d['capdb']['panel'] = 'Geen'
    if d['capdb']['panel'] == 'OVRv1':
        d['genes']['panelsize'] = 0
    if d['genes']['agenen'] == [] and d['genes']['cgenen'] == []:
        d['genes']['agenen'] = d['genes']['genen']

    return render_template('showtest.html', c=d['capdb'],
                           g=d['genes'], caps=caps)

# @app.route('/diagnostiek/nieuw/', methods=['GET', 'POST'])
# def add_test():
#
#     form = NewTestForm()
#     if form.validate_on_submit():
#
#         if not str(form.oid.data).startswith('OID'):
#             form.oid.data = 'OID{}'.format(form.oid.data)
#         if form.pakket.data == '':
#             form.pakket.data = form.capture.data
#         if form.panel.data == '':
#             form.panel.data = 'False'
#
#         sql_info = '''INSERT INTO capdb
#         (genesiscode, aandoening, capture, pakket, panel, OID, lot, actief,
#         verdund, cnvdetectie, printcnv, mozaiekdetectie)
#         VALUES ('{}', '{}', '{}', '{}', '{}', '{}', {}, {}, {}, {}, {}, {})
#         '''.format(form.genesis.data, form.aandoening.data, form.capture.data,
#         form.pakket.data, form.panel.data, form.oid.data, form.lotnummer.data,
#         boolean_to_number(form.actief.data),
#         boolean_to_number(form.verdund.data),
#         boolean_to_number(form.cnvdetectie.data),
#         boolean_to_number(form.printcnv.data),
#         boolean_to_number(form.mozaiekdetectie.data))
#         # print(sql_info, form.genesis.data)
#         T = TargetDatabase(DB)
#         T.change(sql_info)
#         # f = form.capturetarget.data
#         capturetarget = secure_filename(form.capturetarget.data.filename)
#         form.capturetarget.data.save(os.path.join(app.config['UPLOAD_FOLDER'],
#                                                   capturetarget))
#
#         capturegenen = secure_filename(form.capturegenen.data.filename)
#         form.capturegenen.data.save(os.path.join(app.config['UPLOAD_FOLDER'],
#                                                  capturegenen))
#         TF = TargetFiles(str(form.genesis.data), TARGETS,
#                          bedfile=os.path.join(app.config['UPLOAD_FOLDER'],
#                                                   capturetarget))
#         capturegenen =  TF.genelist(os.path.join(app.config['UPLOAD_FOLDER'],
#                                                  capturegenen))
#
#         flash(capturegenen)
#         return redirect(url_for('show_all_tests'))
#
#     return render_template('addtest.html', form=form)


@app.route('/captures/nieuw/', methods=['GET', 'POST'])
def new_capture():
    if request.method == 'POST':
        T = TargetDatabase(DB)
        cap = request.form['capture']
        oid = request.form['oid']
        lot = request.form['lot']
        if 'verdund' in request.form:
            verdund = request.form['verdund']
        elif not 'verdund' in request.form:
            verdund = False
        verdund = boolean_to_number(verdund)
        sql = "INSERT INTO captures {}, {}, {}, {}".format(cap, oid, lot,
                                                            verdund)
        flash(request.form['capture'])
        # T.change(sql)
        return redirect(url_for('new_target', cap=cap, lot=lot, oid=oid, verdund=verdund))

    return render_template('addcapture.html')

@app.route('/captures/nieuw/target/<cap>/<int:lot>/<int:oid>/<verdund>', methods=['GET', 'POST'])
def new_target(cap, lot, oid, verdund):
    if request.method == 'POST':
        pass
        # T = TargetDatabase(DB)
        # cap = request.form['capture']
        # oid = request.form['oid']
        # lot = request.form['lot']
        # verdund = request.form['verdund']
        # sql = "INSERT INTO captures {}, {}, {}, {}".format(cap, oid, lot, verdund)
        # T.change(sql)
    return render_template('addtargets.html', cap=cap, oid=oid, lot=lot, verdund=verdund)


@app.route('/captures/<cap>', methods=['GET', 'POST'])
def show_tests_for_cap(cap):
    T = TargetDatabase(DB)
    tests = T.get_all_tests_for_capture(cap)
    lotnrs = T.get_all_lotnrs_for_capture(cap)
    if request.method == 'POST':
        sql = '''INSERT INTO captures
        (capture, OID, lot, verdund)
        SELECT DISTINCT capture, OID, {}, verdund
        FROM captures
        WHERE capture = '{}'
        '''.format(request.form['lotnr'], cap)
        T.change(sql)
        lotnrs = T.get_all_lotnrs_for_capture(cap)
        return render_template('showcap.html', cap=cap, tests=tests,
                                               lotnrs=lotnrs)
    return render_template('showcap.html', cap=cap, tests=tests,
                                           lotnrs=lotnrs)

@app.route('/createsamplesheet/', methods=['GET', 'POST'])
def upload_labexcel():
    if request.method == 'POST':
        if request.form['samples'] == '':
            flash('Geen input opgegeven')
            return render_template('uploadlabexcel.html')
        if request.form['serie'] == '':
            flash('Geen serienummer opgegeven')
            return render_template('uploadlabexcel.html')

        nullijst_todo = request.form['samples']
        if nullijst_todo:
            uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            with open(os.path.join(uploads, 'samplesheet.tmp'), 'w') as f:
                for line in nullijst_todo.split('\n'):
                    if line:
                        dnr, bc, test = line.split()
                        f.write('{}\t{}\t{}\n'.format(dnr, test, bc))

            S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'), request.form['serie'],
                            os.path.join(uploads, 'SampleSheet.csv'))
            S.write_files()
            return redirect(url_for('uploaded_file', filename='SampleSheet.csv'))

    return render_template('uploadlabexcel.html')


@app.route('/createsamplesheet/created/<filename>')
def uploaded_file(filename):
    return render_template('download.html', filename=filename)

@app.route('/createsamplesheet/<path:filename>')
def download(filename):
    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    return send_from_directory(directory=uploads, filename=filename)
