# Stage 1: Build the application
FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
# Download dependencies first (caching)
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn clean package -DskipTests

# Stage 2: Run the application using Tomcat
FROM tomcat:10.1-jdk17-temurin
# Remove default webapps
RUN rm -rf /usr/local/tomcat/webapps/*
# Copy the built WAR file as ROOT.war
COPY --from=build /app/target/*.war /usr/local/tomcat/webapps/ROOT.war

EXPOSE 8080
# Render will provide the PORT environment variable, but Tomcat defaults to 8080. 
# We can use a script or just let Render map it, but Tomcat's server.xml usually needs adjustment for $PORT.
# However, webapp-runner was easier. Let's stick to webapp-runner in Docker for simplicity with $PORT.

FROM eclipse-temurin:17-jdk
WORKDIR /app
COPY --from=build /app/target/*.war app.war
COPY --from=build /app/target/dependency/webapp-runner.jar webapp-runner.jar

EXPOSE 8080
CMD java $JAVA_OPTS -jar webapp-runner.jar --port ${PORT:-8080} app.war
