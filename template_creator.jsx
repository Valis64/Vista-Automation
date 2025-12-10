#target illustrator

// Automated Print File Template Creator
// Adobe Illustrator ExtendScript (JavaScript)
// This script automates transferring artwork into a print file template.

// Utility functions -----------------------------------------------------
function alertAndExit(message) {
    alert(message);
    throw new Error(message);
}

function waitStep() {
    checkStop();
    try {
        app.redraw();
    } catch (e) {}
    $.sleep(200); // pause to keep Illustrator responsive
}

function waitForDocLoad(doc, steps) {
    steps = steps || 25; // ~5 seconds
    for (var i = 0; i < steps; i++) {
        try {
            doc.pageItems.length; // access to confirm doc is ready
            break;
        } catch (e) {
            waitStep();
        }
    }
    waitStep();
}

function writeProgress(msg) {
    try {
        var scriptDir = File($.fileName).parent;
        var f = File(scriptDir + '/' + PROGRESS_FILE);
        f.encoding = 'UTF-8';
        if (f.open('w')) {
            f.write(msg);
            f.close();
        }
    } catch(e) {}
}

var TEMPLATE_ROOT = 'C:/Users/neone/My Drive (stevan.ybs@gmail.com)/DIE PRINT FILE SETUPS';
var ART_ROOT = '\\MCI2NAS/Art server';
var SHOW_SUMMARY = false;
var DIAGNOSTIC_MODE = false;
var PRESERVE_COLOR_PROFILE = false;
var PRINT_FOLDER_NAME = 'print';
var PROGRESS_FILE = 'jsx_progress.txt';
var PAUSE_FILE = 'jsx_pause.flag';
var CANCEL_FILE = 'jsx_cancel.flag';
var SUMMARY_ARTIFACT = 'last_run.json';
var BLEED_FAILSAFE_SETTINGS = loadBleedFailSafeSettings();

var CANCEL_REQUESTED = false;

function CancelError(message) {
    this.name = 'CancelError';
    this.message = message || 'Cancelled';
}

function isCancelError(err) {
    return err && (err.name === 'CancelError' || err.cancel === true);
}

function checkStop() {
    try {
        var dir = File($.fileName).parent;
        var c = File(dir + '/' + CANCEL_FILE);
        if (c.exists) {
            c.remove();
            CANCEL_REQUESTED = true;
            writeProgress('Cancellation requested');
            throw new CancelError();
        }
        var p = File(dir + '/' + PAUSE_FILE);
        while (p.exists) {
            try { app.redraw(); } catch (e) {}
            $.sleep(500);
            p = File(dir + '/' + PAUSE_FILE);
        }
    } catch (e) {
        if (isCancelError(e)) throw e;
    }
}

function loadTemplateSettings(code) {
    if (!code) return {};
    var scriptDir = File($.fileName).parent;
    var f = File(scriptDir + '/template_settings/' + code.toUpperCase() + '.json');
    if (!f.exists) return {};
    f.encoding = 'UTF-8';
    if (!f.open('r')) return {};
    var txt = f.read();
    f.close();
    var obj = parseJSON(txt);
    return obj || {};
}

function loadBleedFailSafeSettings() {
    var fallback = { defaultRotation: 0, templates: {} };
    var scriptDir = File($.fileName).parent;
    var f = File(scriptDir + '/template_settings/BleedFailSafeSettings.json');
    if (!f.exists) return fallback;
    f.encoding = 'UTF-8';
    if (!f.open('r')) return fallback;
    var txt = f.read();
    f.close();
    var obj = parseJSON(txt);
    if (!obj || typeof obj !== 'object') return fallback;
    var normalized = { defaultRotation: obj.defaultRotation, templates: {} };
    var templates = obj.templates || {};
    if (templates && typeof templates === 'object') {
        for (var key in templates) {
            if (!templates.hasOwnProperty(key)) continue;
            var value = templates[key];
            if (value && typeof value === 'object') {
                normalized.templates[key] = value;
                if (!normalized.templates[key].dieName) normalized.templates[key].dieName = key;
                if (!normalized.templates[key].templateCode) normalized.templates[key].templateCode = key;
            } else if (typeof value === 'number') {
                normalized.templates[key] = { dieName: key, templateCode: key, rotation: value };
            }
        }
    }
    if (typeof obj.defaultRotation === 'number') {
        normalized.defaultRotation = obj.defaultRotation;
    } else if (typeof obj.rotation === 'number') {
        normalized.defaultRotation = obj.rotation;
    }
    if (typeof normalized.defaultRotation !== 'number') normalized.defaultRotation = 0;
    return normalized;
}

var LAM_OPTIONS = [
    { name: 'Matte', color: [255,165,0] },
    { name: 'Gloss', color: [0,128,0] },
    { name: 'SoftTouch', color: [0,0,255] },
    { name: 'Uncoated', color: [255,69,0] },
    { name: 'No Laminate', color: [255,0,0] },
    { name: 'Smudge Proof', color: [0,128,128] }
];

function detectLaminate(text) {
    if (!text) return '';
    var t = String(text).toLowerCase().replace(/\s+/g, '');
    for (var i = 0; i < LAM_OPTIONS.length; i++) {
        var nm = LAM_OPTIONS[i].name.toLowerCase().replace(/\s+/g, '');
        if (t.indexOf(nm) !== -1) return LAM_OPTIONS[i].name;
    }
    return '';
}

function findFileRecursive(folder, name, depth) {
    if (!folder || depth > 10) return null;
    var files = folder.getFiles();
    for (var i = 0; i < files.length; i++) {
        var f = files[i];
        if (f instanceof File) {
            if (f.name.toLowerCase() === name.toLowerCase()) return f;
        } else if (f instanceof Folder) {
            var found = findFileRecursive(f, name, depth + 1);
            if (found) return found;
        }
    }
    return null;
}

function findTemplateFile(name) {
    if (!name) return null;
    var root = new Folder(TEMPLATE_ROOT);
    name = name.toLowerCase();
    function search(folder, depth) {
        if (!folder || depth > 10) return null;
        var files = folder.getFiles();
        for (var i = 0; i < files.length; i++) {
            var f = files[i];
            if (f instanceof File) {
                var nm = f.name.toLowerCase();
                if (nm.indexOf('avp') !== -1 && nm.indexOf(name) !== -1)
                    return f;
            } else if (f instanceof Folder) {
                var found = search(f, depth + 1);
                if (found) return found;
            }
        }
        return null;
    }
    return search(root, 0);
}

function findArtFile(name) {
    if (!name) return null;
    var root = new Folder(ART_ROOT);
    var f = findFileRecursive(root, name, 0);
    if (!f) f = findFileRecursive(root, name + '.ai', 0);
    if (!f) f = findFileRecursive(root, name + '.pdf', 0);
    return f;
}

function getAncestorFolder(entry, generations) {
    if (!entry) return null;
    var current = null;
    if (entry instanceof File || entry instanceof Folder) {
        current = entry.parent;
    }
    if (!current) return null;
    if (generations && generations > 0) {
        while (generations > 0 && current) {
            current = current.parent;
            generations--;
        }
    }
    return current;
}

function downloadHTML(url) {
    var dest = Folder.temp.fsName + '/order_' + Date.now() + '.html';
    var cmd;
    if ($.os.indexOf('Windows') !== -1) {
        cmd = 'cmd /c curl -L -o "' + dest + '" "' + url + '"';
    } else {
        cmd = 'curl -L -o "' + dest + '" "' + url + '"';
    }
    system.callSystem(cmd);
    return dest;
}

function parseJSON(text) {
    try {
        if (typeof JSON !== 'undefined' && JSON.parse) {
            return JSON.parse(text);
        }
    } catch (e) {}
    // Fallback for old ExtendScript without JSON
    try {
        return eval('(' + text + ')');
    } catch (e2) {
        alertAndExit('Failed to parse order_data.json: ' + e2);
    }
    return null;
}

function jsonEscape(str) {
    if (str === null || typeof str === 'undefined') return '';
    var out = String(str);
    out = out.replace(/\\/g, '\\\\');
    out = out.replace(/"/g, '\\"');
    out = out.replace(/\r/g, '\\r');
    out = out.replace(/\n/g, '\\n');
    return out;
}

function twoDigit(num) {
    return (num < 10 ? '0' : '') + num;
}

function toISOStringSafe(date) {
    if (!date) return '';
    return (
        date.getUTCFullYear() + '-' +
        twoDigit(date.getUTCMonth() + 1) + '-' +
        twoDigit(date.getUTCDate()) + 'T' +
        twoDigit(date.getUTCHours()) + ':' +
        twoDigit(date.getUTCMinutes()) + ':' +
        twoDigit(date.getUTCSeconds()) + 'Z'
    );
}

function writeSummaryArtifact(folder, items) {
    if (!folder || !items || !items.length) return;
    try {
        var generated = toISOStringSafe(new Date());
        var lines = [];
        lines.push('{');
        if (generated) {
            lines.push('  "generated_at": "' + jsonEscape(generated) + '",');
        }
        lines.push('  "pairs": [');
        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            lines.push('    {' +
                '"pair": ' + it.pair + ',' +
                ' "art": "' + jsonEscape(it.art) + '",' +
                ' "art_path": "' + jsonEscape(it.artPath || '') + '",' +
                ' "template": "' + jsonEscape(it.template) + '",' +
                ' "template_path": "' + jsonEscape(it.templatePath || '') + '",' +
                ' "filename": "' + jsonEscape(it.filename || '') + '",' +
                ' "flat": "' + jsonEscape(it.flat) + '"' +
            ' }' + (i === items.length - 1 ? '' : ','));
        }
        lines.push('  ]');
        lines.push('}');

        var file = new File(folder.fsName + '/' + SUMMARY_ARTIFACT);
        file.encoding = 'UTF-8';
        if (file.open('w')) {
            file.write(lines.join('\n'));
            file.close();
        }
    } catch (e) {}
}

function loadOrderData(jsonPath) {
    var scriptDir = File($.fileName).parent;
    var f = File(scriptDir + '/' + jsonPath);
    if (!f.exists) alertAndExit('order_data.json not found.');
    f.encoding = 'UTF-8';
    f.open('r');
    var txt = f.read();
    f.close();
    var obj = parseJSON(txt);
    return obj || { items: [] };
}

function parseOrderHTML(path) {
    var f = File(path);
    if (!f.exists) return [];
    f.encoding = 'UTF-8';
    f.open('r');
    var html = f.read();
    f.close();

    var text = html.replace(/\r?\n/g, ' ');

    var filenames = [];
    var infos = [];
    var artNames = [];
    var templateNames = [];
    var lamTypes = [];

    var proof = /<tbody[^>]*id=['"]unordered_proof_items_tbody['"][^>]*>([\s\S]*?)<\/tbody>/i.exec(text);
    if (proof && proof[1]) {
        var block = proof[1];
        var rowRegex = /<tr[^>]*>[\s\S]*?<span[^>]*class=['"]fl_name['"][^>]*>(.*?)<\/span>[\s\S]*?<span[^>]*class=['"]font-11['"][^>]*>(.*?)<\/span>/gi;
        var row;
        while ((row = rowRegex.exec(block)) !== null) {
            if (row.length < 3) continue;
            var fname = String(row[1] || '');
            var infoText = String(row[2] || '');
            fname = fname.replace(/<[^>]+>/g, '').replace(/^\s+|\s+$/g, '');
            infoText = infoText.replace(/<br\s*\/?>(?!$)/gi, ' ');
            infoText = infoText.replace(/<[^>]+>/g, '');
            infoText = infoText.replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '');
            if (fname) filenames.push(fname);
            if (infoText) infos.push(infoText);
        }
    }

    var glues = [];
    var glueRegex = /<strong>\s*Glue tab data\s*<\/strong>[\s\S]*?<\/tr>([\s\S]*?)<\/tbody>/gi;
    var gm;
    while ((gm = glueRegex.exec(text)) !== null) {
        if (gm.length < 2) continue;
        var tdBlock = gm[1];
        var tdRegex = /<tr[^>]*>\s*<td[^>]*>(.*?)<\/td>\s*<\/tr>/gi;
        var t;
        while ((t = tdRegex.exec(tdBlock)) !== null) {
            if (t.length < 2) continue;
            var val = t[1].replace(/<[^>]+>/g, '');
            val = val.replace(/^\s+|\s+$/g, '');
            if (val) glues.push(val);
        }
    }

    var itemBlock = /<tbody[^>]*id=['"]unordered_items_tbody['"][^>]*>([\s\S]*?)<\/tbody>/i.exec(text);
    if (itemBlock && itemBlock[1]) {
        var tblRegex = /<table[^>]*table-inside[^>]*>([\s\S]*?)<\/table>/gi;
        var tbl;
        while ((tbl = tblRegex.exec(itemBlock[1])) !== null) {
            if (tbl.length < 2) continue;
            var chunk = tbl[1];
            var rowMatch = /<tr[^>]*>\s*<td[^>]*><strong>\d+<\/strong><\/td>\s*<td[^>]*><strong>([^<]+)<\/strong><\/td>\s*<td[^>]*><strong>([^<]+)<\/strong>/i.exec(chunk);
            var tempMatch = (rowMatch && rowMatch[1]) ? rowMatch[1] : '';
            var lamMatch = /<span[^>]*style=['"][^>]*>([^<]+)<\/span>/i.exec(chunk);
            var flMatch = /<span[^>]*class=['"]fl_name['"][^>]*>([^<]+)<\/span>/i.exec(chunk);
            var a = (flMatch && flMatch[1]) ? flMatch[1] : '';
            var tCode = tempMatch;
            var lamText = (lamMatch && lamMatch[1]) ? lamMatch[1] : '';
            a = String(a || '').replace(/<[^>]+>/g, '').replace(/^\s+|\s+$/g, '');
            tCode = String(tCode || '').replace(/<[^>]+>/g, '').replace(/^\s+|\s+$/g, '');
            lamText = String(lamText || '').replace(/<[^>]+>/g, '').replace(/^\s+|\s+$/g, '');
            if (a) artNames.push(a);
            if (tCode) templateNames.push(tCode);
            lamTypes.push(detectLaminate(lamText));
        }
    }

    var count = Math.max(filenames.length, infos.length, glues.length, artNames.length, templateNames.length, lamTypes.length);
    var items = [];
    for (var i = 0; i < count; i++) {
        var infoVal = infos[i] || '';
        var lamVal = lamTypes[i] || '';
        if (!lamVal) lamVal = detectLaminate(infoVal);
        items.push({
            filename: filenames[i] || '',
            info: infoVal,
            gluetab: glues[i] || '',
            artName: artNames[i] || '',
            templateName: templateNames[i] || '',
            lamType: lamVal
        });
    }
    return items;
}

function loadInitialOrder() {
    var scriptDir = File($.fileName).parent;
    var jsonFile = File(scriptDir + '/order_data.json');
    if (jsonFile.exists) {
        var obj = loadOrderData('order_data.json');
        if (obj && typeof obj.show_summary !== 'undefined') {
            SHOW_SUMMARY = !!obj.show_summary;
        }
        if (obj && typeof obj.diagnostic !== 'undefined') {
            DIAGNOSTIC_MODE = !!obj.diagnostic;
        }
        if (obj && typeof obj.preserve_color_profile !== 'undefined') {
            PRESERVE_COLOR_PROFILE = !!obj.preserve_color_profile;
        }
        return obj;
    }
    var htmlFile = File(scriptDir + '/order.html');
    if (htmlFile.exists) {
        return { items: parseOrderHTML(htmlFile.fsName), pairs: [] };
    }
    return { items: [], pairs: [] };
}

// Build processing options without showing any dialog. The Python helper
// populates order_data.json with all required information so we simply
// translate that data into the structure expected by the main routine.
function buildOptions(data) {
    var items = data.items || [];
    var pairsInfo = data.pairs || [];
    var out = [];

    function isSkipped(entry) {
        if (!entry) return false;
        var flag = entry.skip;
        return flag === true || flag === 'true' || flag === 1 || flag === '1';
    }

    function getLamOption(name) {
        if (!name) return { name: '', color: [0,0,0] };
        var lower = String(name).toLowerCase();
        for (var i=0; i<LAM_OPTIONS.length; i++) {
            if (LAM_OPTIONS[i].name.toLowerCase() === lower) {
                return LAM_OPTIONS[i];
            }
        }
        return { name: name, color: [0,0,0] };
    }

    for (var i=0; i<pairsInfo.length; i++) {
        var pair = pairsInfo[i] || {};
        var item = items[i] || {};

        if (isSkipped(pair) || isSkipped(item)) {
            continue;
        }

        var lam = getLamOption(pair.lamType || item.lamType);
        var paper = pair.paperType || item.paperType || '';
        out.push({
            artFile: File(pair.art_path),
            templateFile: File(pair.template_path),
            templateCode: pair.template || item.templateName || '',
            laminate: lam,
            paper: paper,
            orderData: {
                info: item.info || '',
                gluetab: item.gluetab || '',
                filename: item.filename || '',
                lamType: lam.name,
                paperType: paper
            }
        });
    }
    return {
        pairs: out,
        vista: false,
        artDir: data.art_dir || ART_ROOT,
        templateDir: data.template_dir || TEMPLATE_ROOT
    };
}

function showSettingsDialog(curArtDir, curTemplateDir){
    var sd = new Window('dialog', 'Settings');

    var artGrp = sd.add('group');
    artGrp.add('statictext', undefined, 'Art Directory:');
    var artInput = artGrp.add('edittext', undefined, curArtDir);
    artInput.characters = 25;
    var artBrowse = artGrp.add('button', undefined, 'Browse');
    artBrowse.onClick = function(){
        var f = Folder.selectDialog('Select artwork directory');
        if (f) artInput.text = f.fsName;
    };

    var tempGrp = sd.add('group');
    tempGrp.add('statictext', undefined, 'Template Directory:');
    var tempInput = tempGrp.add('edittext', undefined, curTemplateDir);
    tempInput.characters = 25;
    var tempBrowse = tempGrp.add('button', undefined, 'Browse');
    tempBrowse.onClick = function(){
        var f = Folder.selectDialog('Select template directory');
        if (f) tempInput.text = f.fsName;
    };

    var btns = sd.add('group');
    btns.alignment = 'right';
    var ok = btns.add('button', undefined, 'OK', {name:'ok'});
    var cancel = btns.add('button', undefined, 'Cancel', {name:'cancel'});
    ok.onClick = function(){ sd.close(1); };
    cancel.onClick = function(){ sd.close(0); };

    if(sd.show() != 1) return null;
    return { artDir: artInput.text, templateDir: tempInput.text };
}

function showInputDialog(orderItems, pairInfo) {
    var dlg = new Window('dialog', 'Print Template Creator');

    var loadedItems = orderItems || [];
    pairInfo = pairInfo || [];


    var tabPanel = dlg.add('tabbedpanel');
    tabPanel.alignChildren = 'fill';

    var pages = [];
    var columnsPerPage = 3;
    var pairsPerColumn = 3;
    var pairsPerPage = columnsPerPage * pairsPerColumn;

    function getPage(index) {
        var pageIdx = Math.floor(index / pairsPerPage);
        while (pages.length <= pageIdx) {
            var t = tabPanel.add('tab', undefined, 'Page ' + (pages.length + 1));
            t.orientation = 'row';
            t.alignChildren = 'top';
            t.columns = [];
            pages.push(t);
        }
        return pages[pageIdx];
    }

    function getColumn(idx) {
        var page = getPage(idx);
        var idxInPage = idx % pairsPerPage;
        var colIdx = Math.floor(idxInPage / pairsPerColumn);
        while (page.columns.length <= colIdx) {
            var c = page.add('group');
            c.orientation = 'column';
            c.alignChildren = 'left';
            page.columns.push(c);
        }
        return page.columns[colIdx];
    }

    var lamOptions = LAM_OPTIONS;
    var pairs = [];
    var lastLamIndex = 0;
    var lastPaperIndex = 0;
    var lastTemplatePath = '';

    function renumberPairs(){
        for (var i = 0; i < pairs.length; i++) {
            var col = getColumn(i);
            try {
                if (pairs[i].grp.parent !== col) {
                    pairs[i].grp.parent = col;
                }
            } catch (e) {
                // fallback if parent property is read-only
                try {
                    col.add(pairs[i].grp);
                } catch(_) {}
            }
            pairs[i].updateIndex(i + 1);
        }
        for (var p = pages.length - 1; p >= 0; p--) {
            var page = pages[p];
            for (var j = page.columns.length - 1; j >= 0; j--) {
                if (page.columns[j].children.length === 0) {
                    page.columns[j].remove();
                    page.columns.splice(j, 1);
                }
            }
            if (page.columns.length === 0) {
                page.remove();
                pages.splice(p, 1);
            } else {
                page.text = 'Page ' + (p + 1);
            }
        }
    }

    function addPair(orderData, info) {
        var num = pairs.length + 1;
        var col = getColumn(num - 1);
        var grp = col.add('panel', undefined, 'Pair ' + num);
        grp.orientation = 'column';
        grp.alignChildren = 'left';

        var prefixGrp = grp.add('group');
        prefixGrp.add('statictext', undefined, 'Name:');
        prefixGrp.add('statictext', undefined, '.' + num);

        var fileGrp = grp.add('group');
        fileGrp.add('statictext', undefined, 'Art:');
        var artInput = fileGrp.add('edittext', undefined, '');
        artInput.characters = 25;
        var artPath = '';
        var artBtn = fileGrp.add('button', undefined, 'Browse');
        artBtn.onClick = function () {
            var f = File.openDialog('Select artwork file (AI/PDF)', '*.ai;*.pdf');
            if (f) {
                artPath = f.fsName;
                artInput.text = File(f).name;
            }
        };

        fileGrp.add('statictext', undefined, 'Template:');
        var tempInput = fileGrp.add('edittext', undefined, '');
        tempInput.characters = 25;
        var templatePath = lastTemplatePath;
        if (templatePath) tempInput.text = File(templatePath).name;
        var tempBtn = fileGrp.add('button', undefined, 'Browse');
        tempBtn.onClick = function () {
            var f2 = File.openDialog('Select print file template (AI/PDF)', '*.ai;*.pdf');
            if (f2) {
                templatePath = f2.fsName;
                lastTemplatePath = templatePath;
                tempInput.text = File(f2).name;
            }
        };

        var lamGrp = grp.add('group');
        lamGrp.add('statictext', undefined, 'Laminate:');
        var checks = [];
        var selectedLam = lamOptions[lastLamIndex].name;
        var selectedColor = lamOptions[lastLamIndex].color;
        function chooseLam(idx) {
            for (var i = 0; i < checks.length; i++) checks[i].value = i === idx;
            selectedLam = lamOptions[idx].name;
            selectedColor = lamOptions[idx].color;
            lastLamIndex = idx;
        }
        for (var l = 0; l < lamOptions.length; l++) {
            checks[l] = lamGrp.add('checkbox', undefined, lamOptions[l].name);
            var sz = checks[l].preferredSize;
            if (sz && sz.height) {
                checks[l].preferredSize.height = sz.height * 2;
            } else {
                checks[l].preferredSize = [150, 30];
            }
            checks[l].onClick = (function(i){ return function(){ chooseLam(i); }; })(l);
        }
        chooseLam(lastLamIndex);
        if (orderData && orderData.lamType) {
            for (var li=0; li<lamOptions.length; li++) {
                if (lamOptions[li].name.toLowerCase() === orderData.lamType.toLowerCase()) {
                    chooseLam(li);
                    break;
                }
            }
        }

        var paperGrp = grp.add('group');
        paperGrp.add('statictext', undefined, 'Paper:');
        var paperChecks = [];
        var paperNames = ['10in', '11in', '13in'];
        var selectedPaper = paperNames[lastPaperIndex];
        function choosePaper(idx) {
            for (var i = 0; i < paperChecks.length; i++) paperChecks[i].value = i === idx;
            selectedPaper = paperNames[idx];
            lastPaperIndex = idx;
        }
        for (var p = 0; p < paperNames.length; p++) {
            paperChecks[p] = paperGrp.add('checkbox', undefined, paperNames[p]);
            paperChecks[p].onClick = (function(i){ return function(){ choosePaper(i); }; })(p);
        }
        choosePaper(lastPaperIndex);
        if (orderData && orderData.paperType) {
            for (var pi=0; pi<paperNames.length; pi++) {
                if (paperNames[pi].toLowerCase() === String(orderData.paperType).toLowerCase()) {
                    choosePaper(pi);
                    break;
                }
            }
        }

        var infoGrp = grp.add('group');
        infoGrp.alignChildren = 'left';
        infoGrp.add('statictext', undefined, 'Info:');
        var infoDisplay = infoGrp.add('edittext', undefined,
            orderData ? orderData.info : '', { readonly: true, multiline: true });
        infoDisplay.characters = 60;
        infoDisplay.preferredSize.height = 40;

        var glueGrp = grp.add('group');
        glueGrp.alignChildren = 'left';
        glueGrp.add('statictext', undefined, 'GlueTab:');
        var glueDisplay = glueGrp.add('edittext', undefined,
            orderData ? orderData.gluetab : '', { readonly: true, multiline: true });
        glueDisplay.characters = 60;
        glueDisplay.preferredSize.height = 40;

        var fileGrp2 = grp.add('group');
        fileGrp2.alignChildren = 'left';
        fileGrp2.add('statictext', undefined, 'File:');
        var fileDisplay = fileGrp2.add('edittext', undefined,
            orderData ? orderData.filename : '', { readonly: true, multiline: true });
        fileDisplay.characters = 60;
        fileDisplay.preferredSize.height = 40;

        var delGrp = grp.add('group');
        delGrp.alignment = 'right';
        var delBtn = delGrp.add('button', undefined, 'Delete Pair');
        var addPairBtn = delGrp.add('button', undefined, 'Add Pair');
        var pairOkBtn = delGrp.add('button', undefined, 'OK');
        pairOkBtn.onClick = handleOk;

        var pairObj = {
            grp: grp,
            artInput: artInput,
            templateInput: tempInput,
            fileDisplay: fileDisplay,
            orderData: orderData || null,
            setPaths: function(a, t){
                if (a) { artPath = a; artInput.text = File(a).name; }
                if (t) { templatePath = t; lastTemplatePath = t; tempInput.text = File(t).name; }
            },
            artPath: function(){ return artPath; },
            templatePath: function(){ return templatePath; },
            getLam: function(){ return { name: selectedLam, color: selectedColor }; },
            getPaper: function(){ return selectedPaper; },
            setOrderData: function(data){
                if (data) {
                    infoDisplay.text = data.info;
                    glueDisplay.text = data.gluetab;
                    fileDisplay.text = data.filename;
                    if (data.lamType) {
                        for (var i=0;i<lamOptions.length;i++) {
                            if (lamOptions[i].name.toLowerCase() === data.lamType.toLowerCase()) {
                                chooseLam(i);
                                break;
                            }
                        }
                    }
                    if (data.paperType) {
                        for (var i2=0;i2<paperNames.length;i2++) {
                            if (paperNames[i2].toLowerCase() === String(data.paperType).toLowerCase()) {
                                choosePaper(i2);
                                break;
                            }
                        }
                    }
                }
            },
            getOrderData: function(){
                return {
                    info: infoDisplay.text,
                    gluetab: glueDisplay.text,
                    filename: fileDisplay.text,
                    lamType: selectedLam,
                    paperType: selectedPaper
                };
            },
            updateIndex: function(n){
                grp.text = 'Pair ' + n;
                prefixGrp.children[1].text = '.' + n;
            },
            remove: function(){
                var idx = pairs.indexOf(pairObj);
                if (idx >= 0){
                    pairs.splice(idx,1);
                    grp.remove();
                    renumberPairs();
                    dlg.layout.layout(true);
                }
            }
        };
        delBtn.onClick = pairObj.remove;
        addPairBtn.onClick = function(){
            var idx = pairs.length;
            var data = loadedItems[idx];
            var info = pairInfo[idx];
            addPair(data, info);
            dlg.layout.layout(true);
        };
        if(orderData) pairObj.setOrderData(orderData);
        if(info) pairObj.setPaths(info.art_path, info.template_path);
        pairs.push(pairObj);
        renumberPairs();
    }

    // preload first pair if available

    addPair(loadedItems[0], pairInfo[0]);

    var btnRow = dlg.add('group');
    btnRow.orientation = 'row';
    btnRow.alignment = 'fill';

    var addBtn = btnRow.add('button', undefined, 'Add Pair');
    addBtn.onClick = function () {
        var idx = pairs.length;
        var data = loadedItems[idx];
        var info = pairInfo[idx];
        addPair(data, info);
        dlg.layout.layout(true);
    };



    var settingsBtn = btnRow.add('button', undefined, 'Settings');
    settingsBtn.onClick = function(){
        var res = showSettingsDialog(ART_ROOT, TEMPLATE_ROOT);
        if(res){
            ART_ROOT = res.artDir;
            TEMPLATE_ROOT = res.templateDir;
        }
    };

    var vistaCheck = dlg.add('checkbox', undefined, 'Vista');

    var btnGrp = dlg.add('group');
    btnGrp.alignment = 'right';
    var ok = btnGrp.add('button', undefined, 'OK', { name: 'ok' });
    var cancel = btnGrp.add('button', undefined, 'Cancel', { name: 'cancel' });

    function setHighlight(field, flag) {
        try {
            var g = field.graphics;
            var c = flag ? [1, 0.6, 0.6] : [1, 1, 1];
            g.backgroundColor = g.newBrush(g.BrushType.SOLID_COLOR, c);
        } catch(e) {}
    }

    function handleOk() {
        var mismatches = [];
        for (var i = 0; i < pairs.length; i++) {
            setHighlight(pairs[i].artInput, false);
            setHighlight(pairs[i].fileDisplay, false);
            var artName = pairs[i].artInput.text.replace(/\.[^.]+$/, '');
            var fileTxt = pairs[i].fileDisplay.text || '';
            if (fileTxt.toLowerCase().indexOf(artName.toLowerCase()) === -1) {
                mismatches.push(i + 1);
                setHighlight(pairs[i].artInput, true);
                setHighlight(pairs[i].fileDisplay, true);
            }
        }
        if (mismatches.length > 0) {
            alert('Art filename must be contained in the File field for pair(s): ' + mismatches.join(', ') + '.');
            return;
        }
        for (var i = 0; i < pairs.length; i++) {
            if (!pairs[i].artPath() || !pairs[i].templatePath()) {
                alert('Please choose both files for pair ' + (i + 1));
                return;
            }
            var lam = pairs[i].getLam();
            if (!lam.name) {
                alert('Please choose a laminate type for pair ' + (i + 1));
                return;
            }
            if (!pairs[i].getPaper()) {
                alert('Please choose a paper type for pair ' + (i + 1));
                return;
            }
        }
        dlg.close(1);
    }

    ok.onClick = handleOk;
    cancel.onClick = function () { dlg.close(0); };

    if (dlg.show() != 1) alertAndExit('Operation cancelled.');

    var files = [];
    for (var j = 0; j < pairs.length; j++) {
        files.push({
            artFile: File(pairs[j].artPath()),
            templateFile: File(pairs[j].templatePath()),
            laminate: pairs[j].getLam(),
            paper: pairs[j].getPaper(),
            orderData: pairs[j].getOrderData()
        });
    }

    return {
        pairs: files,
        vista: vistaCheck.value,
        artDir: ART_ROOT,
        templateDir: TEMPLATE_ROOT
    };
}

function colorMatch(color, c, m, y, k, tol) {
    if (!color) return false;
    if (color.typename === 'SpotColor') {
        if (color.spot && color.spot.name.toLowerCase() === 'bleed') color = color.spot.color;
        else color = color.spot.color;
    }
    if (color.typename !== 'CMYKColor') return false;
    tol = tol || 1;
    return Math.abs(Math.round(color.cyan) - c) <= tol &&
           Math.abs(Math.round(color.magenta) - m) <= tol &&
           Math.abs(Math.round(color.yellow) - y) <= tol &&
           Math.abs(Math.round(color.black) - k) <= tol;
}

function isArtBleedColor(color, tol) {
    if (!color) return false;
    if (usesBleedSpot(color)) return true;
    tol = tol || 1;
    return colorMatch(color, 100, 0, 100, 0, tol) || colorMatch(color, 0, 100, 100, 0, tol);
}

function isTemplateBleedColor(color, tol) {
    if (!color) return false;
    if (usesBleedSpot(color)) return true;
    tol = tol || 1;
    return colorMatch(color, 100, 0, 100, 0, tol) || colorMatch(color, 0, 100, 100, 0, tol);
}

function makeRGBColor(r, g, b) {
    var c = new RGBColor();
    c.red = r; c.green = g; c.blue = b;
    return c;
}

function hasBleedName(item) {
    if (!item) return false;
    if (item.name && item.name.toLowerCase() === 'bleed') return true;
    if (item.layer && item.layer.name && item.layer.name.toLowerCase() === 'bleed') return true;
    return false;
}

function collectBleedPaths(doc, colorFn) {
    var paths = [];
    for (var k = 0; k < doc.pathItems.length; k++) {
        var p = doc.pathItems[k];
        if (p.hidden || p.locked) continue;
        if (p.stroked && (colorFn(p.strokeColor) || hasBleedName(p))) {
            paths.push(p);
        }
    }
    return paths;
}

function findBleedSpot(doc) {
    if (!doc) return null;
    var i;
    if (doc.spots && doc.spots.length) {
        for (i = 0; i < doc.spots.length; i++) {
            var spot = doc.spots[i];
            if (spot && spot.name && spot.name.toLowerCase() === 'bleed') {
                return spot;
            }
        }
    }
    if (doc.swatches && doc.swatches.length) {
        for (i = 0; i < doc.swatches.length; i++) {
            var sw = doc.swatches[i];
            if (!sw) continue;
            var swName = (sw.name || '').toLowerCase();
            if (swName === 'bleed' && sw.color && sw.color.typename === 'SpotColor' && sw.color.spot) {
                return sw.color.spot;
            }
            if (sw.color && sw.color.typename === 'SpotColor' && sw.color.spot &&
                sw.color.spot.name && sw.color.spot.name.toLowerCase() === 'bleed') {
                return sw.color.spot;
            }
        }
    }
    return null;
}

function ensureBleedSpot(doc) {
    if (!doc) return null;
    var bleed = findBleedSpot(doc);
    if (!bleed) {
        bleed = doc.spots.add();
        bleed.name = 'Bleed';
        bleed.colorType = ColorModel.SPOT;
    }
    var cmyk = new CMYKColor();
    cmyk.cyan = 0;
    cmyk.magenta = 100;
    cmyk.yellow = 100;
    cmyk.black = 0;
    bleed.color = cmyk;
    return bleed;
}

function makeSpotBleedColor(doc) {
    var spot = ensureBleedSpot(doc);
    var sc = new SpotColor();
    sc.spot = spot;
    sc.tint = 100;
    return sc;
}

function getBleedFailSafeRotation(templateCode) {
    var code = templateCode ? String(templateCode).toUpperCase() : '';
    if (BLEED_FAILSAFE_SETTINGS.templates && code) {
        var entry = BLEED_FAILSAFE_SETTINGS.templates[code];
        if (typeof entry === 'number') {
            return entry;
        }
        if (entry && typeof entry.rotation === 'number') {
            return entry.rotation;
        }
    }
    if (typeof BLEED_FAILSAFE_SETTINGS.rotation === 'number') {
        return BLEED_FAILSAFE_SETTINGS.rotation;
    }
    if (typeof BLEED_FAILSAFE_SETTINGS.defaultRotation === 'number') {
        return BLEED_FAILSAFE_SETTINGS.defaultRotation;
    }
    return 0;
}

function usesBleedSpot(color, spot) {
    if (!color || color.typename !== 'SpotColor' || !color.spot) return false;
    var colorSpot = color.spot;
    var colorSpotName = (colorSpot.name || '').toLowerCase();
    if (spot && colorSpot === spot) return true;
    if (colorSpotName === 'bleed') return true;
    if (spot && spot.name && colorSpotName === spot.name.toLowerCase()) return true;
    if (colorSpot.color && colorSpot.color.typename === 'CMYKColor' &&
        colorMatch(colorSpot.color, 0, 100, 100, 0, 0)) {
        return true;
    }
    return false;
}

function findBleedPath(doc, colorFn, createLayer) {
    var bleedGroup;
    var bleedLayer = null;
    if (createLayer) {
        bleedLayer = doc.layers.add();
        bleedLayer.name = 'Bleed_Layer';
        bleedGroup = bleedLayer.groupItems.add();
    } else {
        bleedGroup = doc.groupItems.add();
    }

    // First try: look for the Bleed spot color directly
    var bleedSpot = findBleedSpot(doc);
    if (bleedSpot) {
        for (var s = 0; s < doc.pathItems.length; s++) {
            var spotPath = doc.pathItems[s];
            if (spotPath.hidden || spotPath.locked) continue;
            if (!spotPath.stroked) continue;
            if (usesBleedSpot(spotPath.strokeColor, bleedSpot)) {
                spotPath.move(bleedGroup, ElementPlacement.PLACEATEND);
                return bleedGroup;
            }
        }
    }

    var tries = [1, 3, 5];
    var paths = [];
    for (var t = 0; t < tries.length && paths.length === 0; t++) {
        paths = collectBleedPaths(doc, function(c){ return colorFn(c, tries[t]); });
    }

    for (var i = 0; i < paths.length; i++) {
        paths[i].move(bleedGroup, ElementPlacement.PLACEATEND);
    }

    if (bleedGroup.pageItems.length === 0) {
        if (bleedLayer) {
            bleedLayer.remove();
        } else {
            bleedGroup.remove();
        }
        return null;
    }
    return bleedGroup;
}

function findTopBleedPath(doc, createLayer) {
    if (doc.pathItems.length === 0) return null;
    var bleedGroup;
    var bleedLayer = null;
    if (createLayer) {
        bleedLayer = doc.layers.add();
        bleedLayer.name = 'Bleed_Layer';
        bleedGroup = bleedLayer.groupItems.add();
    } else {
        bleedGroup = doc.groupItems.add();
    }
    var p = doc.pathItems[doc.pathItems.length - 1];
    p.move(bleedGroup, ElementPlacement.PLACEATEND);
    if (bleedGroup.pageItems.length === 0) {
        if (bleedLayer) {
            bleedLayer.remove();
        } else {
            bleedGroup.remove();
        }
        return null;
    }
    return bleedGroup;
}

function runBleedFailSafe(artworkDoc, templateFile, templateCode) {
    var result = { bleedGroup: null, templateDoc: null };
    if (!artworkDoc || !templateFile) return result;

    writeProgress('Bleed not found. Running fail-safe recovery.');
    var templateDoc = app.open(templateFile);
    waitForDocLoad(templateDoc);
    result.templateDoc = templateDoc;

    var templateBleedPath = findLargestBleedPath(templateDoc, isTemplateBleedColor);
    if (!templateBleedPath) {
        templateDoc.close(SaveOptions.DONOTSAVECHANGES);
        alertAndExit('Bleed paths not found.');
    }

    var bleedLayer = artworkDoc.layers.add();
    bleedLayer.name = 'Bleed_Layer';
    var bleedGroup = bleedLayer.groupItems.add();
    var duplicate = templateBleedPath.duplicate(bleedGroup, ElementPlacement.PLACEATEND);
    if (!duplicate) {
        bleedLayer.remove();
        templateDoc.close(SaveOptions.DONOTSAVECHANGES);
        alertAndExit('Failed to duplicate template bleed path.');
    }

    duplicate.name = 'Bleed';
    duplicate.hidden = false;
    duplicate.locked = false;
    duplicate.stroked = true;
    duplicate.strokeColor = makeSpotBleedColor(artworkDoc);

    var artboardRect = getArtboardRect(artworkDoc);
    centerItemOnArtboard(bleedGroup, artboardRect);

    var rotation = getBleedFailSafeRotation(templateCode);
    if (rotation) {
        bleedGroup.rotate(rotation, true, true, true, true, Transformation.CENTER);
    }

    result.bleedGroup = bleedGroup;
    writeProgress('  Fail-safe bleed recreated');
    return result;
}

function getBleedBounds(doc, colorFn) {
    var b = getBleedBoundsIn(doc, colorFn);
    if (!b) alertAndExit('Bleed paths not found.');
    return b;
}

function findLargestBleedPath(container, colorFn) {
    var best = null;
    var bestArea = 0;
    for (var i = 0; i < container.pathItems.length; i++) {
        var p = container.pathItems[i];
        if (p.stroked && (colorFn(p.strokeColor) || hasBleedName(p))) {
            var b = p.geometricBounds;
            var area = Math.abs(b[2] - b[0]) * Math.abs(b[1] - b[3]);
            if (!best || area > bestArea) {
                best = p;
                bestArea = area;
            }
        }
    }
    return best;
}

function getBleedBoundsIn(container, colorFn) {
    var best = null;
    var bestArea = 0;
    for (var i = 0; i < container.pathItems.length; i++) {
        var p = container.pathItems[i];
        if (p.stroked && (colorFn(p.strokeColor) || hasBleedName(p))) {
            var b = p.geometricBounds;
            var area = Math.abs(b[2] - b[0]) * Math.abs(b[1] - b[3]);
            if (!best || area > bestArea) {
                best = b;
                bestArea = area;
            }
        }
    }
    return best;
}

function getMaskBounds(group) {
    if (!group || !group.pageItems) return null;
    for (var i = 0; i < group.pageItems.length; i++) {
        var it = group.pageItems[i];
        if (it.typename === 'PathItem' && it.clipping) {
            return it.geometricBounds;
        }
        if (
            it.typename === 'CompoundPathItem' &&
            it.pathItems.length > 0 &&
            it.pathItems[0].clipping
        ) {
            return it.pathItems[0].geometricBounds;
        }
    }
    return group.geometricBounds;
}

function normalizeAlignment(alignment) {
    if (!alignment || typeof alignment !== 'string') return 'center';
    var key = alignment.toLowerCase();
    switch (key) {
        case 'top-left':
        case 'top-center':
        case 'top-right':
        case 'center-left':
        case 'center':
        case 'center-right':
        case 'bottom-left':
        case 'bottom-center':
        case 'bottom-right':
            return key;
        default:
            return 'center';
    }
}

function getBoundsAnchor(bounds, alignment) {
    var left = bounds[0];
    var top = bounds[1];
    var right = bounds[2];
    var bottom = bounds[3];
    var centerX = (left + right) / 2;
    var centerY = (top + bottom) / 2;
    switch (alignment) {
        case 'top-left':
            return [left, top];
        case 'top-center':
            return [centerX, top];
        case 'top-right':
            return [right, top];
        case 'center-left':
            return [left, centerY];
        case 'center-right':
            return [right, centerY];
        case 'bottom-left':
            return [left, bottom];
        case 'bottom-center':
            return [centerX, bottom];
        case 'bottom-right':
            return [right, bottom];
        case 'center':
        default:
            return [centerX, centerY];
    }
}

function getArtboardRect(doc) {
    if (!doc || !doc.artboards || doc.artboards.length === 0) return null;
    var active = doc.artboards[doc.artboards.getActiveArtboardIndex()];
    for (var i = 0; i < doc.artboards.length; i++) {
        var ab = doc.artboards[i];
        if (ab.name && ab.name.toLowerCase() === 'art') {
            active = ab;
            break;
        }
    }
    return active.artboardRect;
}

function centerItemOnArtboard(item, rect) {
    if (!item || !rect) return;
    var bounds = item.visibleBounds;
    var itemCenterX = (bounds[0] + bounds[2]) / 2;
    var itemCenterY = (bounds[1] + bounds[3]) / 2;
    var rectCenterX = (rect[0] + rect[2]) / 2;
    var rectCenterY = (rect[1] + rect[3]) / 2;
    item.translate(rectCenterX - itemCenterX, rectCenterY - itemCenterY);
}

function alignGroupToPath(group, path, alignment) {
    if (!path) return;
    var maskB = getMaskBounds(group);
    if (!maskB) return;
    var targetB = path.geometricBounds;
    var resolvedAlignment = normalizeAlignment(alignment);
    var sourceAnchor = getBoundsAnchor(maskB, resolvedAlignment);
    var targetAnchor = getBoundsAnchor(targetB, resolvedAlignment);
    var dx = targetAnchor[0] - sourceAnchor[0];
    var dy = targetAnchor[1] - sourceAnchor[1];
    group.translate(dx, dy);
}

function getBottomArtLayer(doc) {
    var artLayer = null;
    for (var i = 0; i < doc.layers.length; i++) {
        var nm = doc.layers[i].name.toLowerCase();
        if (nm === 'art' || nm === 'artwork') {
            artLayer = doc.layers[i];
            break;
        }
    }
    if (!artLayer) {
        for (var j = doc.layers.length - 1; j >= 0; j--) {
            var nm2 = doc.layers[j].name.toLowerCase();
            if (nm2.indexOf('art') !== -1) {
                artLayer = doc.layers[j];
                break;
            }
        }
    }
    if (!artLayer) {
        artLayer = doc.layers.add();
        artLayer.name = 'art';
    }
    if (artLayer !== doc.layers[doc.layers.length - 1]) {
        artLayer.move(doc, ElementPlacement.PLACEATEND);
    }
    return artLayer;
}

function createClippingGroup(doc, bleedGroup) {
    if (bleedGroup.pathItems.length === 0) {
        alertAndExit('No bleed path for clipping');
    }
    var mask = bleedGroup.pathItems[0];
    var bestArea = 0;
    for (var i = 0; i < bleedGroup.pathItems.length; i++) {
        var p = bleedGroup.pathItems[i];
        var b = p.visibleBounds;
        var area = Math.abs(b[2] - b[0]) * Math.abs(b[1] - b[3]);
        if (area > bestArea) {
            bestArea = area;
            mask = p;
        }
    }

    var topLevelItems = [];
    for (var li = 0; li < doc.layers.length; li++) {
        var layer = doc.layers[li];
        var layerItems = layer.pageItems;
        for (var pi = 0; pi < layerItems.length; pi++) {
            var item = layerItems[pi];
            if (item.parent === layer) {
                topLevelItems.push(item);
            }
        }
    }

    var grp = doc.groupItems.add();
    for (var i = topLevelItems.length - 1; i >= 0; i--) {
        topLevelItems[i].move(grp, ElementPlacement.PLACEATEND);
    }

    mask.move(grp, ElementPlacement.PLACEATBEGINNING);
    mask.clipping = true;
    grp.clipped = true;
    grp.selected = true;
    // Return the grouped artwork so it can be duplicated into the template
    return grp;
}

function findNamedItem(doc, name) {
    var target = name.toLowerCase().replace(/\s+/g, '');
    for (var i = 0; i < doc.pageItems.length; i++) {
        var it = doc.pageItems[i];
        if (it.name) {
            var nm = it.name.toLowerCase().replace(/\s+/g, '');
            if (nm === target) {
                return it;
            }
        }
    }
    return null;
}

function addLaminateLabel(doc, bleedBounds, lamName, lamColorArr) {
    if (!lamName) return;

    var lamItem = findNamedItem(doc, 'laminate');
    var x, y, w, h;
    if (lamItem) {
        var lb = lamItem.visibleBounds; // [left, top, right, bottom]
        x = (lb[0] + lb[2]) / 2;
        y = (lb[1] + lb[3]) / 2;
        w = Math.abs(lb[2] - lb[0]);
        h = Math.abs(lb[1] - lb[3]);
    } else {
        var b = bleedBounds;
        x = b[2] + 36;
        y = b[1] + 36;
        w = 60;
        h = 20;
    }

    var tf = doc.textFrames.add();
    tf.contents = lamName;
    tf.position = [x, y];
    tf.textRange.characterAttributes.fillColor = makeRGBColor(lamColorArr[0], lamColorArr[1], lamColorArr[2]);

    if (w && h) {
        var tb = tf.visibleBounds;
        var tw = Math.abs(tb[2] - tb[0]);
        var th = Math.abs(tb[1] - tb[3]);
        if (tw > 0 && th > 0) {
            var wScale = (w / tw) * 100;
            var hScale = (h / th) * 100;
            tf.resize(wScale, hScale);
        }
        tf.position = [x, y];
        try { tf.paragraphs[0].justification = Justification.CENTER; } catch(e){}
    }
}



function main() {
    var data = loadInitialOrder();
    writeProgress('Preparing order data');
    if (data.art_dir) ART_ROOT = data.art_dir;
    if (data.template_dir) TEMPLATE_ROOT = data.template_dir;
    var opts = buildOptions(data);

    if (opts.artDir) ART_ROOT = opts.artDir;
    if (opts.templateDir) TEMPLATE_ROOT = opts.templateDir;

    var summaryItems = [];
    var summaryFolder = null;
    if (data.summary_dir) {
        summaryFolder = Folder(data.summary_dir);
        try { if (!summaryFolder.exists) summaryFolder.create(); } catch(e) {}
    }

    var cancelled = false;
    try {
        for (var p = 0; p < opts.pairs.length; p++) {
            checkStop();
            var pair = opts.pairs[p];
            var summaryItem = null;
            var err = null;
            for (var attempt = 0; attempt < 3; attempt++) {
                checkStop();
                try {
                    writeProgress('Processing pair ' + (p + 1) + ' of ' + opts.pairs.length);
                    waitStep();
                    summaryItem = processPair(pair, p);
                    break;
                } catch(e) {
                    if (isCancelError(e)) throw e;
                    err = e;
                    writeProgress('Retry ' + (attempt + 1) + ' failed: ' + e);
                }
            }
            if (!summaryItem) {
                alertAndExit('Failed to process pair ' + (p + 1) + ': ' + err);
            }
            summaryItems.push(summaryItem);
        }
    } catch (e) {
        if (isCancelError(e)) {
            cancelled = true;
        } else {
            throw e;
        }
    }

    var summary = 'Processed ' + summaryItems.length + ' pair';
    if (summaryItems.length !== 1) summary += 's';
    summary += '\n\n';
    for (var si = 0; si < summaryItems.length; si++) {
        var it = summaryItems[si];
        summary += 'Pair ' + it.pair + ': ' + it.art + ' -> ' + it.template + '\n';
        summary += '  Info: ' + it.info + '\n';
        summary += '  GlueTab: ' + it.gluetab + '\n';
        summary += '  Laminate: ' + it.laminate + '  Paper: ' + it.paper + '\n';
        summary += '  lines PDF: ' + it.lines + '\n';
        summary += '  flat PDF: ' + it.flat + '\n\n';
    }

    if (summaryFolder) {
        writeProgress('Saving summary artifact');
        writeSummaryArtifact(summaryFolder, summaryItems);
    }

    if (summaryFolder && SHOW_SUMMARY) {
        writeProgress('Writing summary');
        try {
            var autoFile = new File(summaryFolder.fsName + '/Automation Summary.txt');
            autoFile.encoding = 'UTF-8';
            if (autoFile.open('w')) {
                autoFile.write(summary);
                autoFile.close();
            }
        } catch(e) {}
    }

    if (SHOW_SUMMARY) {
        var sumDlg = new Window('palette', 'Summary');
        sumDlg.orientation = 'column';
        sumDlg.alignChildren = 'fill';
        var sumBox = sumDlg.add('edittext', undefined, summary, {readonly:true, multiline:true});
        sumBox.preferredSize = [500, 300];
        var btnG = sumDlg.add('group');
        btnG.alignment = 'right';
        var saveBtn = btnG.add('button', undefined, 'Save Summary');
        var closeBtn = btnG.add('button', undefined, 'Close');
        saveBtn.onClick = function(){
            var f = File.saveDialog('Save summary as', '*.txt');
            if (f) {
                f.encoding = 'UTF-8';
                if (f.open('w')) {
                    f.write(summary);
                    f.close();
                    alert('Summary saved to ' + f.fsName);
                }
            }
        };
        closeBtn.onClick = function(){ sumDlg.close(); };
        sumDlg.show();
        $.sleep(3000);
        try { if (sumDlg.visible) sumDlg.close(); } catch(e) {}
    }

    waitStep();

    return cancelled;
}

function processPair(pair, index) {
    var orderData = pair.orderData || { info: '', gluetab: '', filename: '' };

    writeProgress('Opening artwork "' + pair.artFile.name + '"');
    var artworkDoc = app.open(pair.artFile);
    waitForDocLoad(artworkDoc);
    writeProgress('  Artwork loaded');

    var tmplName = pair.templateFile.name.toLowerCase();
    var isCD0434 = tmplName.indexOf('cd0434') !== -1;
    var isPB001 = tmplName.indexOf('pb001') !== -1;
    var isPB005 = tmplName.indexOf('pb005') !== -1;
    var settings = loadTemplateSettings(pair.templateCode);
    var rawAlignment = (settings && typeof settings.alignment === 'string') ? settings.alignment : null;
    var alignment = normalizeAlignment(rawAlignment || 'center');
    if (rawAlignment && rawAlignment.toLowerCase() !== alignment) {
        writeProgress('Alignment "' + rawAlignment + '" not recognized. Using ' + alignment + '.');
    }

    writeProgress('Finding bleed path in artwork');
    var templateDoc = null;
    var bleedGroup = isCD0434 ?
        findTopBleedPath(artworkDoc, true) :
        findBleedPath(artworkDoc, isArtBleedColor, true);
    if (!bleedGroup) {
        var failSafe = runBleedFailSafe(artworkDoc, pair.templateFile, pair.templateCode);
        bleedGroup = failSafe.bleedGroup;
        templateDoc = failSafe.templateDoc;
    }
    if (!bleedGroup) alertAndExit('Bleed paths not found.');
    waitStep();
    writeProgress('  Bleed path located');

    writeProgress('Creating clipping mask');
    var clipGroup = createClippingGroup(artworkDoc, bleedGroup);
    waitStep();
    writeProgress('  Clip group created');

    if (templateDoc) {
        writeProgress('Template already open from fail-safe');
    } else {
        writeProgress('Opening template "' + pair.templateFile.name + '"');
        templateDoc = app.open(pair.templateFile);
        waitForDocLoad(templateDoc);
        writeProgress('  Template opened');
    }

    if (artworkDoc.documentColorSpace !== templateDoc.documentColorSpace) {
        var artSpace = artworkDoc.documentColorSpace == DocumentColorSpace.RGB ? 'RGB' : 'CMYK';
        var tempSpace = templateDoc.documentColorSpace == DocumentColorSpace.RGB ? 'RGB' : 'CMYK';
        if (PRESERVE_COLOR_PROFILE) {
            alertAndExit('Color mode mismatch: artwork is ' + artSpace + ' but template is ' + tempSpace);
        } else {
            writeProgress('  Converting artwork to ' + tempSpace);
            artworkDoc.activate();
            if (templateDoc.documentColorSpace == DocumentColorSpace.CMYK) {
                app.executeMenuCommand('doc-color-cmyk');
            } else {
                app.executeMenuCommand('doc-color-rgb');
            }
        }
    }

    writeProgress('Locating template bleed path');
    // Find the template bleed path before pasting so artwork colors don't
    // interfere with detection
    var templateBleedPath = findLargestBleedPath(templateDoc, isTemplateBleedColor);
    if (!templateBleedPath) throw new Error('Bleed paths not found.');
    var templateBleedBounds = templateBleedPath.geometricBounds;
    waitStep();
    writeProgress('  Template bleed located');

    var bleedPaths = [];
    if (settings.bleedPaths && settings.bleedPaths.length) {
        for (var si = 0; si < settings.bleedPaths.length; si++) {
            var bp = findNamedItem(templateDoc, settings.bleedPaths[si]);
            if (bp) bleedPaths.push(bp);
        }
    }
    if (bleedPaths.length === 0) {
        if (isCD0434) {
            writeProgress('Detecting coffee sleeve bleed lines');
            for (var bi = 1; bi <= 12; bi++) {
                var bp2 = findNamedItem(templateDoc, 'bleed' + bi);
                if (bp2) bleedPaths.push(bp2);
            }
        } else if (isPB001) {
            writeProgress('Detecting PB001 bleed lines');
            var bp1 = findNamedItem(templateDoc, 'bleed1');
            var bp2b = findNamedItem(templateDoc, 'bleed2');
            if (bp1) bleedPaths.push(bp1);
            if (bp2b) bleedPaths.push(bp2b);
        }
    }
    if (bleedPaths.length === 0) bleedPaths.push(templateBleedPath);

    writeProgress('Duplicating artwork');
    for (var bi2 = 0; bi2 < bleedPaths.length; bi2++) {
        var artLayer = getBottomArtLayer(templateDoc);
        writeProgress('  Paste copy #' + (bi2 + 1));
        var pasted = clipGroup.duplicate(artLayer, ElementPlacement.PLACEATEND);
        if (!pasted) {
            templateDoc.close(SaveOptions.DONOTSAVECHANGES);
            artworkDoc.close(SaveOptions.DONOTSAVECHANGES);
            throw new Error('Failed to duplicate artwork.');
        }
        var rot = typeof settings.rotation === 'number' ? settings.rotation : (isCD0434 ? 90 : ((isPB001 || isPB005) ? 180 : 0));
        if (rot) {
            if (rot === 90 && settings.rotation === undefined && isCD0434) {
                writeProgress('  Rotating for coffee sleeve');
                pasted.rotate(90);
            } else {
                writeProgress('  Rotating ' + rot + '°');
                pasted.rotate(rot, true, true, true, true, Transformation.CENTER);
            }
        }
        if (settings.mirror) {
            writeProgress('  Mirroring artwork');
            pasted.resize(-100, 100, true, true, true, true, 100, Transformation.CENTER);
        }
        var scale = (typeof settings.artworkScale === 'number') ? settings.artworkScale : 1;
        if (scale && scale !== 1) {
            writeProgress('  Scaling artwork to ' + Math.round(scale * 100) + '%');
            pasted.resize(scale * 100, scale * 100, true, true, true, true, scale * 100, Transformation.CENTER);
        }
        waitStep();

        writeProgress('Aligning artwork (' + alignment + ')');
        alignGroupToPath(pasted, bleedPaths[bi2], alignment);
        waitStep();
        writeProgress('  Alignment done');
    }

    writeProgress('Closing artwork');
    artworkDoc.close(SaveOptions.DONOTSAVECHANGES);
    waitStep();
    writeProgress('  Artwork closed');

    writeProgress('  Updating info text');
    var proofing = orderData.info;
    if (proofing) {
        for (var i2 = 0; i2 < templateDoc.textFrames.length; i2++) {
            var tf = templateDoc.textFrames[i2];
            if (tf.name && tf.name.toLowerCase() === 'info') {
                tf.contents = proofing;
                break;
            }
        }
    }
    waitStep();

    writeProgress('  Resetting version text');
    for (var v = 0; v < templateDoc.textFrames.length; v++) {
        var tv = templateDoc.textFrames[v];
        if (tv.contents.match(/V\d+/i)) {
            tv.contents = 'V1';
            break;
        }
    }
    waitStep();

    writeProgress('  Applying glue tab data');
    var glueData = orderData.gluetab;
    if (glueData) {
        for (var g = 0; g < templateDoc.textFrames.length; g++) {
            var tg = templateDoc.textFrames[g];
            if (tg.name && tg.name.toLowerCase() === 'gluetab') {
                tg.contents = glueData;
            }
        }
    }
    waitStep();

    writeProgress('  Adding laminate label');
    addLaminateLabel(templateDoc, templateBleedBounds, pair.laminate.name, pair.laminate.color);
    waitStep();

    var baseName;
    var templateCode = pair.templateCode ? String(pair.templateCode) : '';
    var templateName = (pair.templateFile && pair.templateFile.name) ? String(pair.templateFile.name) : '';
    var isPTemplate = false;
    if (templateCode.length > 0) {
        var normalizedCode = templateCode.replace(/^\s+|\s+$/g, '').toUpperCase();
        if (normalizedCode.length > 0 && normalizedCode.indexOf('PB') !== 0 && normalizedCode.charAt(0) === 'P') {
            isPTemplate = true;
        }
    }
    if (!isPTemplate && templateName.length > 0) {
        var normalizedName = templateName.replace(/^\s+|\s+$/g, '').toUpperCase();
        if (normalizedName.length > 0 && normalizedName.indexOf('PB') !== 0 && normalizedName.charAt(0) === 'P') {
            isPTemplate = true;
        }
    }
    var destRoot = getAncestorFolder(pair.artFile, isPTemplate ? 2 : 1);
    if (destRoot && !(destRoot instanceof Folder)) {
        destRoot = new Folder(destRoot);
    }
    if (orderData.filename) {
        if (destRoot) {
            var folderName = DIAGNOSTIC_MODE ? '--DO NOT USE - PRINT--' : PRINT_FOLDER_NAME;
            var printFolder = new Folder(destRoot.fsName + '/' + folderName);
            if (!printFolder.exists) printFolder.create();
            baseName = printFolder.fsName + '/' + orderData.filename.replace(/\.pdf$/i, '');
        } else {
            baseName = pair.templateFile.path + '/' + orderData.filename.replace(/\.pdf$/i, '');
        }
    } else {
        var saveFile = File.saveDialog('Save print file as', '*.pdf');
        if (!saveFile) {
            templateDoc.close(SaveOptions.DONOTSAVECHANGES);
            return null;
        }
        var folder = saveFile.path;
        var name = saveFile.name.replace(/\.pdf$/i, '');
        baseName = folder + '/' + name;
    }

    // Remove any existing "lines" suffix from the base name
    baseName = baseName.replace(/(?:_lines|\s+lines)$/i, '');

    writeProgress('Saving PDFs for pair ' + (index + 1));
    var pdfOpts = new PDFSaveOptions();
    pdfOpts.compatibility = PDFCompatibility.ACROBAT8;
    pdfOpts.embedICCProfile = true;
    var destProfile = templateDoc.documentColorSpace == DocumentColorSpace.RGB ?
        templateDoc.rgbProfile : templateDoc.cmykProfile;
    pdfOpts.colorConversionID = ColorConversion.COLORCONVERSIONREPURPOSE;
    pdfOpts.destinationProfile = destProfile;
    writeProgress('  Saving lines PDF');
    var linesPath = baseName + '_lines_' + pair.paper + '.pdf';
    templateDoc.saveAs(File(linesPath), pdfOpts);
    writeProgress('  Saved ' + linesPath);
    var templateLayer = templateDoc.layers['template'];
    waitStep();
    if (templateLayer) {
        writeProgress('  Hiding template layer');
        templateLayer.visible = false;
    }
    writeProgress('  Saving flat PDF');
    var flatPath = baseName + '_flat_' + pair.paper + '.pdf';
    templateDoc.saveAs(File(flatPath), pdfOpts);
    writeProgress('  Saved ' + flatPath);
    waitStep();

    writeProgress('Closing template');
    templateDoc.close(SaveOptions.DONOTSAVECHANGES);
    writeProgress('  Template closed');
    writeProgress('Finished pair ' + (index + 1));
    waitStep();

    return {
        pair: index + 1,
        art: pair.artFile.name,
        template: pair.templateFile.name,
        info: orderData.info,
        gluetab: orderData.gluetab,
        laminate: pair.laminate.name,
        paper: pair.paper,
        lines: baseName + '_lines_' + pair.paper + '.pdf',
        flat: baseName + '_flat_' + pair.paper + '.pdf',
        artPath: pair.artFile ? pair.artFile.fsName : '',
        templatePath: pair.templateFile ? pair.templateFile.fsName : '',
        filename: orderData.filename || ''
    };
}

var MAIN_CANCELLED = false;

try {
    MAIN_CANCELLED = main();
} catch (e) {
    if (isCancelError(e)) {
        MAIN_CANCELLED = true;
    } else {
        throw e;
    }
}

function markDone(){
    try {
        var scriptDir = File($.fileName).parent;
        var f = File(scriptDir + '/jsx_done.flag');
        f.encoding = 'UTF-8';
        if (f.open('w')) {
            f.write('done');
            f.close();
        }
    } catch(e) {}
}

if (MAIN_CANCELLED || CANCEL_REQUESTED) {
    writeProgress('Cancelled');
} else {
    writeProgress('Complete');
}
markDone();
if (MAIN_CANCELLED || CANCEL_REQUESTED) {
    try { $.exit(); } catch (e) {}
}
