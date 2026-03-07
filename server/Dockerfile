# Stage 1: Build the application
FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
# Download dependencies first (caching)
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn clean package -DskipTests

# Stage 2: Run the application using Tomcat 10
FROM tomcat:10.1-jdk17-temurin
WORKDIR /usr/local/tomcat

# Remove default webapps
RUN rm -rf webapps/*

# Copy the built WAR file as ROOT.war so it serves at /
COPY --from=build /app/target/*.war webapps/ROOT.war

# Render provides the PORT environment variable.
# We modify Tomcat's server.xml to listen on the port provided by Render.
# If $PORT is not set, it defaults to 8080.
CMD ["sh", "-c", "sed -i 's/port=\"8080\"/port=\"'${PORT:-8080}'\"/g' conf/server.xml && catalina.sh run"]
