"""
Skills that imply other skills: a directed graph, walked breadth-first.

    Next.js ──> React ──> JavaScript
    Django  ──> Python
    GitHub  ──> Git

If a resume names Django, the person knows Python, even if the word "Python"
never appears. infer_skills() collects everything reachable from the skills
a resume does name.
"""

from collections import deque

from analysis.matcher import SKILL_CATEGORY

# WHY so conservative: an edge A -> B means "nobody realistically uses A
# without working knowledge of B". Direction is the whole point: React
# implies JavaScript, but JavaScript does not imply React. A wrong-way or
# merely likely edge marks skills as covered that the person may never have
# used, which inflates the score and makes the tool lie. So edges that are
# only usually true are left out: .NET (could be F# or VB), Playwright (has
# Python and Java bindings), Storybook (works with several frameworks).
IMPLIES = {
    # Languages
    "TypeScript": ["JavaScript"],
    # Frontend
    "Next.js": ["React"],
    "React Native": ["React"],
    "React Testing Library": ["React"],
    "React Query": ["React"],
    "Zustand": ["React"],
    "Material UI": ["React"],
    "shadcn/ui": ["React", "Tailwind CSS"],
    "React": ["JavaScript"],
    "Nuxt.js": ["Vue.js"],
    "Vue.js": ["JavaScript"],
    "Angular": ["JavaScript"],
    "Svelte": ["JavaScript"],
    "jQuery": ["JavaScript"],
    "Redux": ["JavaScript"],
    "Three.js": ["JavaScript"],
    "D3.js": ["JavaScript"],
    "Jest": ["JavaScript"],
    "Vitest": ["JavaScript"],
    "Cypress": ["JavaScript"],
    "Tailwind CSS": ["CSS"],
    "Bootstrap": ["CSS"],
    "Sass": ["CSS"],
    "Flutter": ["Dart"],
    # Backend
    "Node.js": ["JavaScript"],
    "Express.js": ["Node.js"],
    "NestJS": ["Node.js", "TypeScript"],
    "tRPC": ["TypeScript"],
    "Prisma": ["ORM"],
    "Django": ["Python", "ORM"],
    "Flask": ["Python"],
    "FastAPI": ["Python"],
    "Celery": ["Python"],
    "Spring Boot": ["Java"],
    "Hibernate": ["Java", "ORM"],
    "Laravel": ["PHP"],
    "Ruby on Rails": ["Ruby"],
    # Databases
    "PostgreSQL": ["SQL"],
    "MySQL": ["SQL"],
    "MariaDB": ["SQL"],
    "SQLite": ["SQL"],
    "SQL Server": ["SQL"],
    "Oracle Database": ["SQL"],
    "BigQuery": ["SQL"],
    "Snowflake": ["SQL"],
    "Supabase": ["PostgreSQL"],
    "MongoDB": ["NoSQL"],
    "Cassandra": ["NoSQL"],
    "DynamoDB": ["NoSQL", "AWS"],
    # DevOps & tools
    "GitHub": ["Git"],
    "GitLab": ["Git"],
    "GitHub Actions": ["GitHub", "CI/CD"],
    "Jenkins": ["CI/CD"],
    "Helm": ["Kubernetes"],
    "Kubernetes": ["Docker"],
    # Concepts
    "TDD": ["Unit Testing"],
}


def validate_graph(graph):
    """Raise ValueError if an edge names an unknown skill or points at itself."""
    for source, targets in graph.items():
        if source not in SKILL_CATEGORY:
            raise ValueError(f"Implication graph names unknown skill {source!r}")
        for target in targets:
            if target not in SKILL_CATEGORY:
                raise ValueError(f"Implication graph edge {source!r} -> {target!r} names an unknown skill")
            if target == source:
                raise ValueError(f"Implication graph has a self-edge on {source!r}")


# WHY validate at import: skills are matched by exact canonical name, so a typo
# like "Nextjs" would make an edge silently never fire. Failing when the app
# (or the test suite in CI) starts catches it immediately.
validate_graph(IMPLIES)


def infer_skills(found_skills, graph=IMPLIES):
    """
    Skills implied by found_skills that aren't in found_skills themselves.

    Returns {inferred skill: chain from the found skill that implies it}:
        infer_skills({"Next.js"}) -> {"React": ["Next.js", "React"],
                                      "JavaScript": ["Next.js", "React", "JavaScript"]}

    This is a multi-source breadth-first search: every found skill starts in
    the queue together, so each inferred skill is reached through the
    shortest chain from the nearest skill the resume actually names.
    """
    found = set(found_skills)

    # WHY a visited set, seeded with the found skills: if the graph ever gains
    # an edge back the way it came (A -> B -> A), a traversal without one
    # loops forever. Seeding it with the found skills also means a skill the
    # resume names outright is never reported as merely inferred.
    visited = set(found)
    chains = {}

    # Sorted so the same resume always explains an inferred skill the same way.
    queue = deque([skill] for skill in sorted(found))
    while queue:
        chain = queue.popleft()
        current = chain[-1]
        for neighbour in graph.get(current, []):
            if neighbour in visited:
                continue
            visited.add(neighbour)
            neighbour_chain = chain + [neighbour]
            chains[neighbour] = neighbour_chain
            queue.append(neighbour_chain)
    return chains
