FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY . .
RUN chmod +x gradlew \
 && ./gradlew :app:installDist --no-daemon --no-configuration-cache

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/app/build/install/app/ ./
EXPOSE 8080
CMD ["./bin/app"]
