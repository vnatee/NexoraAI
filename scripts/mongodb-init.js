const databaseName = String(process.env.NEXORA_MONGO_DB_NAME || "").trim();
const applicationUsername = String(process.env.NEXORA_MONGO_APP_USERNAME || "").trim();
const applicationPassword = String(process.env.NEXORA_MONGO_APP_PASSWORD || "");

if (!databaseName || !applicationUsername || !applicationPassword) {
    throw new Error("NexoraAI MongoDB application database and credentials are required");
}

const applicationDatabase = db.getSiblingDB(databaseName);
if (!applicationDatabase.getUser(applicationUsername)) {
    applicationDatabase.createUser({
        user: applicationUsername,
        pwd: applicationPassword,
        roles: [{ role: "readWrite", db: databaseName }]
    });
}
