# INVENTORY AND THREAT MODEL

## 1. IDENTITY
- **Project Name:** SmartServe (Sistema Inteligente de Gestão para Restaurantes)
- **Team:** Debuggers (Jala University - Cohort 7)
- **Audit Date:** 2026-09-15
- **Auditor:** project-audit (AI Agent)

## 2. TARGET PROJECT
- **State Audited:** Repository HEAD
- **Target Commit:** `TARGET_COMMIT = f7798ca700166e618389c1d1a9037a1ab2c32e7e`
- **Files Mapped:** 168

## 3. CURRENT ENVIRONMENT
- **OS:** Linux
- **Working Tree:** Clean
- **Context:** Academic/Learning environment

## 4. STACK
- **Language:** Java 21
- **Backend Framework:** Javalin (7.2.2)
- **Build System:** Maven (Compiler 3.15.0)
- **Database:** PostgreSQL (15.1)
- **Database Access:** JDBC (Driver 42.7.7) + HikariCP (5.1.0)
- **Authentication:** Java-JWT (4.5.2) + BCrypt (0.10.2)
- **Frontend:** Vanilla HTML5, CSS3, JavaScript
- **Infrastructure:** Docker, Docker Compose
- **Web Server (Frontend):** Nginx

## 5. GENERAL ARCHITECTURE
O sistema é um monólito com separação clássica em camadas (Controller, Service, DAO, Model). A API backend expõe endpoints REST que são consumidos diretamente pelo frontend servido via Nginx. A comunicação com o banco de dados é feita via JDBC puro, com DAOs gerenciando as conexões injetadas por uma `ConnectionFactory` alimentada por variáveis de ambiente.

## 6. THREAT MODEL CONTEXT
O sistema gerencia operações centrais de um restaurante: pedidos, estoque, e acesso de funcionários. 
- **Atores:** Garçom, Cozinheiro, Estoquista, Caixa, Administrador.
- **Ameaças Principais:**
  - Manipulação indevida de pedidos (ex: alterar pedidos de outro garçom, pular etapas).
  - Acesso indevido a dados de funcionários (privilégio escalado).
  - Injeção de SQL nos endpoints de busca e atualização.
  - Exposição de senhas/tokens via interceptação.

## 7. GLOBAL LIMITATIONS
- **Testing:** Nenhuma suíte de testes (unitários, de integração ou e2e) foi detectada no repositório. Runtime tests not executed.
- **Production Configuration:** A configuração de produção não está disponível; a análise baseia-se em `docker-compose.yml` e configuração de ambiente local.
- **Dependency CVE Analysis:** Dependency CVE analysis not executed.
