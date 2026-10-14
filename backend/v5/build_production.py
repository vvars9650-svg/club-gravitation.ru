"""Prepare a distinct PROD candidate package. Never invokes cloud deployment."""
import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from .build_deployment import build_deployment_zip

WRAPPER = '''import json, os
from v5.handler import handler as _handler
def handler(event, context=None):
    if os.getenv("V5_ENVIRONMENT") != "PROD":
        return {"statusCode":503,"headers":{"Content-Type":"application/json"},"body":json.dumps({"error":{"code":"prod_package_environment_required"}})}
    return _handler(event, context)
'''


def build_production_zip(output_path):
    output_path=Path(output_path).resolve()
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='production-candidate-') as tmp:
        base=build_deployment_zip(Path(tmp)/'base.zip')
        with zipfile.ZipFile(base) as source, zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED) as target:
            digests={}
            for name in source.namelist():
                content=WRAPPER.encode() if name=='index.py' else source.read(name)
                target.writestr(name,content)
                digests[name]=hashlib.sha256(content).hexdigest()
            root=Path(__file__).resolve().parents[2]
            sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
            dirty=subprocess.check_output(['git','status','--porcelain','--','backend/v5'],cwd=root,text=True).strip()
            manifest={'target':'PROD','source_head':sha,'source_dirty':bool(dirty),'provenance_snapshot':'b306cf4a4a94cc92395485d8986c445c070d2c42','short_form_legal_gate':'CLOSED','approved_legal_baseline':['PPD-2.2','CONSENT-PD-2.2','FORM-2.2'],'files':digests}
            target.writestr('DEPLOYMENT-MANIFEST.json',json.dumps(manifest,sort_keys=True,indent=2))
    return output_path


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'dist'/'production-rc.zip')
    print(build_production_zip(parser.parse_args().output))
