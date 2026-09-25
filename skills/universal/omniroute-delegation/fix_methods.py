with open("src/omniroute_delegation/task_builder.py", "r") as f:
    content = f.read()

content = content.replace("def objetivo(", "def objective(")
content = content.replace("def restricoes(", "def constraints(")
content = content.replace("def contexto(", "def context(")
content = content.replace("def formato(", "def format(")
content = content.replace("def criterios(", "def criteria(")
content = content.replace("def perfil(", "def profile(")

with open("src/omniroute_delegation/task_builder.py", "w") as f:
    f.write(content)
