"""Role presets reuse the seed JDs. Keys match frontend/src/lib/interviewRoles.js."""

from analysis.demo import default_seed_dir, parse_jd_file

ROLE_FILES = {
    "frontend": "jd_frontend.txt",
    "backend": "jd_backend.txt",
    "fullstack": "jd_fullstack.txt",
    "sde_fresher": "jd_sde_fresher.txt",
}


def load_role(role):
    title, _company, text = parse_jd_file(default_seed_dir() / ROLE_FILES[role])
    return title, text
