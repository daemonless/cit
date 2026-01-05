VERSION ?= 0.2.1
RELEASE_NAME = cit-$(VERSION)

.PHONY: release clean test

release:
	mkdir -p dist/$(RELEASE_NAME)
	cp cit dist/$(RELEASE_NAME)/
	cp screenshot.py dist/$(RELEASE_NAME)/
	cp verify.py dist/$(RELEASE_NAME)/
	chmod +x dist/$(RELEASE_NAME)/cit
	cd dist && tar czf $(RELEASE_NAME).tar.gz $(RELEASE_NAME)
	@echo "Created dist/$(RELEASE_NAME).tar.gz"

clean:
	rm -rf dist/

test:
	./cit ghcr.io/daemonless/radarr:latest --port 7878 --health /ping \
		--annotation 'org.freebsd.jail.allow.mlock=true' \
		--screenshot /tmp/cit-test.png --verify -v
