import os
import re
import json
from collections import OrderedDict

from flask import Flask
from flask import render_template, flash, redirect, url_for, request
from flask import send_from_directory
from werkzeug.utils import secure_filename
import config as cfg
from ngsscriptlibrary import TargetDatabase
from ngsscriptlibrary import TargetAnnotation
from ngsscriptlibrary import SampleSheet
from ngsscriptlibrary import get_picard_header, boolean_to_number

app = Flask(__name__)
app.secret_key = 'super secret key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'uploads'

HOME = cfg.HOME
TARGETS = cfg.TARGETS
DB = cfg.DB
MYSQLUSER = cfg.MYSQLUSER



@app.route('/')
@app.route('/index/')
def intro():
    return render_template('index.html')


@app.route('/index/database/')
def database_explained():
    return render_template('database_explanation.html')


@app.route('/nieuw/')
def new_menu():
    return render_template('new.html')


@app.route('/diagnostiek/')
def show_all_tests():
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    tests.sort()
    d = OrderedDict()
    for test in tests:
        d[test] = T.get_info_for_genesis(test)
    return render_template('showalltests.html', tests=d)


@app.route('/diagnostiek/<genesis>')
def show_testinfo(genesis):
    T = TargetDatabase(DB)
    tests = T.get_all_tests()
    if genesis not in tests:
        flash('{} niet gevonden'.format(test))
        return redirect(url_for('show_all_tests'))

    d = dict()
    d['captures'] = dict()
    d['pakketten'] = dict()
    d['panels'] = dict()

    caps = T.get_all_captures_for_genesis(genesis)
    caps = [T.get_all_versions_for_capture(cap) for cap in caps]
    for cap in caps:
        for vcap in cap:
            d['captures'][vcap] = T.get_all_info_for_vcapture(vcap)

    pakketten = T.get_all_pakketten_for_genesis(genesis)
    pakketten = [T.get_all_versions_for_pakket(p) for p in pakketten]
    for p in pakketten:
        for vp in p:
            d['pakketten'][vp] = T.get_all_info_for_vpakket(vp)

    panels = T.get_all_panels_for_genesis(genesis)
    panels = [T.get_all_versions_for_panel(p) for p in panels]
    for p in panels:
        if p is None: continue
        for vp in p:
            d['panels'][vp] = T.get_all_info_for_vpanel(vp)
    todo_list = T.get_info_for_genesis(genesis)
    return render_template('showtest.html', info=d, todo=todo_list)


@app.route('/diagnostiek/nieuw/')
def add_test():
    captures = TargetDatabase(DB).get_all_captures()
    return render_template('addtest.html', captures=captures)


@app.route('/captures/nieuw/linktest/', methods=['GET', 'POST'])
def link_test():
    T = TargetDatabase(DB)
    captures = T.get_all_captures()
    tests = T.get_all_tests()
    return render_template('addexistingtest.html',
                           captures=captures, tests=tests)

@app.route('/captures/<cap>', methods=['GET', 'POST'])
def show_tests_for_cap(cap):
    pass

@app.route('/captures/nieuw/', methods=['GET', 'POST'])
def new_capture():
    if request.method == 'POST':
        T = TargetDatabase(DB)
        cap = request.form['capture'].lower()
        oid = request.form['oid']
        lot = request.form['lot']
        vcap = re.search(r'v\d+$', cap)
        if vcap is not None:
            re.sub(r'v\d+$', cap)
        if 'verdund' in request.form:
            verdund = request.form['verdund']
        elif 'verdund' not in request.form:
            verdund = False
        cap = cap.upper()
        verdund = boolean_to_number(verdund)
        allcaptures = T.get_all_captures()
        if not cap in allcaptures:
            versie = 1
        elif cap in allcaptures:
            versies = T.get_all_versions_for_capture(cap)
            versies = [_.split('v')[1] for _ in versies]
            versies.sort()
            versie = int(versies[-1]) + 1
        sql = """INSERT INTO captures (capture, versie, OID, lot, verdund, grootte)
                 VALUES ('{}', {}, {}, {}, {}, 0)
                 """.format(cap, versie, oid, lot, verdund)
        flash('{} toegevoegd aan database'.format(request.form['capture']))
        flash(sql)
        T.change(sql)
        return redirect(url_for('new_target', cap='{}v{}'.format(cap, versie)))

    return render_template('addcapture.html')

@app.route('/captures/nieuw/target/<cap>', methods=['GET', 'POST'])
def new_target(cap):
    if request.method == 'POST':
        capture, versie = cap.split('v')
        targetrepo = os.path.join(TARGETS, capture)
        if not os.path.isdir(targetrepo):
            os.system('mkdir -p {}'.format(targetrepo))
        genelist = request.form['genen'].split()
        targetfile = request.files['targetfile']
        name = '{}_exonplus20.bed'.format(cap)
        targetfile.save(os.path.join(targetrepo, name))
        targetfile = os.path.join(targetrepo, name)
        T = TargetAnnotation(bedfile=targetfile, genes=genelist,
                             host='localhost', user=MYSQLUSER, db='annotation')
        notfound, notrequested = T.report_genecomp()
        annotated_bed = T.annotate_bed_and_filter_genes()
        annotated_bed_file = os.path.join(targetrepo,
                                          name.replace('.bed', '.annotated'))
        capsize = 0
        with open(annotated_bed_file, 'w') as f:
            for line in annotated_bed:
                chromosome, start, end, gene = line
                f.write('{}\t{}\t{}\t{}\n'.format(chromosome, start, end, gene))
                size = int(end) - int(start)
                capsize += size

        generegion_file = os.path.join(targetrepo,
                                       '{}_generegions.bed'.format(cap))
        with open(generegion_file, 'w') as f:
            for gene in genelist:
                for region in T.get_region(gene):
                    chromosome, start, end = region
                    f.write('{}\t{}\t{}\n'.format(chromosome, start, end))

        picardheader = get_picard_header()
        picard_file = os.path.join(targetrepo,
                                       '{}_targets.interval_list'.format(cap))
        with open(picard_file, 'w') as f:
            for line in picardheader:
                f.write(line)
            for line in annotated_bed:
                chromosome, start, end, gene = line
                f.write('{}\t{}\t{}\t+\t{}\n'.format(chromosome,
                                                         start, end, cap))
        sql = '''UPDATE captures
        SET grootte={}, genen='{}'
        WHERE (capture='{}' AND versie={})
        '''.format(capsize, json.dumps(genelist), capture, versie)
        TargetDatabase(DB).change(sql)
        return render_template('newcapreport.html', notfound=notfound,
                                                    notrequested=notrequested,
                                                    cap=cap)

    return render_template('addtargets.html', cap=cap)


@app.route('/captures/<cap>', methods=['GET', 'POST'])
def show_capture(cap):
    capture, versie = cap.split('v')
    return render_template('index.html')

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

            S = SampleSheet(os.path.join(uploads, 'samplesheet.tmp'),
                            request.form['serie'],
                            os.path.join(uploads, 'SampleSheet.csv'))
            S.write_files()
            return redirect(url_for('uploaded_file',
                                    filename='SampleSheet.csv'))

    return render_template('uploadlabexcel.html')


@app.route('/createsamplesheet/created/<filename>')
def uploaded_file(filename):
    return render_template('download.html', filename=filename)


@app.route('/createsamplesheet/<path:filename>')
def download(filename):
    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    return send_from_directory(directory=uploads, filename=filename)


if __name__ == '__main__':
    app.run(debug=True)
